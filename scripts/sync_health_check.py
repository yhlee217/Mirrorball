"""수집이 멈췄는지 맥 밖에서 확인한다 — GitHub Actions 가 매일 실행.

왜 맥 밖인가
    수집이 조용히 멈춘 걸 두 번 당했고, 두 번 다 '맥 안에서만 보이는 신호'였다.
      2026-08     프리플라이트가 runs/collect.out.log 에만 외쳤다
      2026-09~10  크로미움이 사라져 일요일 5번이 전부 죽었다 → 5주치 공백
    맥이 꺼져 있어도, 크로미움이 없어도, 알림을 놓쳐도 걸리는 감시자가 필요하다.

곁따라오는 효과
    Supabase 무료 플랜은 API 요청이 일정 기간 없으면 프로젝트를 일시정지한다.
    주 1회 수집은 그 기준과 간격이 거의 같아 여유가 없다 — 이 일일 호출이
    그 타이머를 매일 리셋한다.

권한
    sync_jobs 를 직접 읽지 않고 0022_sync_health.sql 의 security definer 함수만
    호출한다. 그래서 anon 키로 충분하고(이미 웹 번들에 공개된 키), 고객 정보에는
    닿을 수 없다.

종료 코드
    0  정상
    1  수집 지연 — Actions 실행이 실패로 뜨고 저장소 소유자에게 메일이 간다

사용:
    SUPABASE_URL=... SUPABASE_ANON_KEY=... python3 scripts/sync_health_check.py
    STALE_DAYS=8    지연 판정 기준(기본 8)
    ALERT_WEBHOOK   (선택) 설정하면 지연 시 JSON 을 POST 한다
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# 수집은 일요일 1회다. 정상이면 '마지막 성공으로부터'는 최대 7일(일요일 수집 직전)이므로
# 8 이상은 예정된 일요일이 통째로 빈 것이다. web/lib/sync.ts 의 isSyncStale 과 같은 기준.
DEFAULT_STALE_DAYS = 8
TIMEOUT = 30


def evaluate(rows: list[dict], stale_days: float) -> list[dict]:
    """지연된 테넌트만 돌려준다. 네트워크와 분리해 두어 테스트가 가능하다.

    days_since 가 None 인 경우(= 성공 기록이 한 번도 없음)도 지연으로 본다 —
    '아직 한 번도 안 됐다'를 조용히 넘기면 설치 직후 실패를 영원히 모른다.
    """
    late = []
    for r in rows:
        d = r.get("days_since")
        if d is None or float(d) >= stale_days:
            late.append(r)
    return late


def _fmt(r: dict) -> str:
    d = r.get("days_since")
    days = "기록 없음" if d is None else f"{float(d):.1f}일 전"
    return f"  {r.get('slug', '?'):12s} 마지막 성공 {str(r.get('last_ok') or '-')[:19]:19s} ({days})"


def fetch(url: str, key: str) -> list[dict]:
    req = urllib.request.Request(
        url.rstrip("/") + "/rest/v1/rpc/sync_health",
        data=b"{}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (고정 호스트)
        return json.loads(r.read().decode("utf-8"))


def notify(webhook: str, late: list[dict], stale_days: float) -> None:
    """지연 알림을 외부로. 저장소가 공개라 로그에 남는 문구는 일부러 중립적으로 쓴다."""
    body = json.dumps({
        "text": "Mirrorball 데이터 갱신이 "
                f"{stale_days:g}일 이상 지연됐습니다 ({len(late)}곳). 맥 수집 작업을 확인해주세요.",
        "detail": [{"slug": r.get("slug"), "days_since": r.get("days_since")} for r in late],
    }).encode("utf-8")
    try:
        req = urllib.request.Request(webhook, data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT):
            pass
        print("  알림 전송됨")
    except Exception as exc:  # noqa: BLE001 — 알림 실패가 판정을 덮지 않게
        print(f"  알림 전송 실패(판정은 유효): {exc}")


def main() -> int:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        print("X SUPABASE_URL / SUPABASE_ANON_KEY 가 없습니다 (저장소 Secrets 확인)")
        return 1
    stale_days = float(os.environ.get("STALE_DAYS") or DEFAULT_STALE_DAYS)

    try:
        rows = fetch(url, key)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        print(f"X 조회 실패 HTTP {exc.code}: {detail}")
        if exc.code in (401, 403, 404):
            print("  → 0022_sync_health.sql 을 적용했는지 확인하세요(함수가 없거나 권한 없음)")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"X 조회 실패: {exc}  (프로젝트가 일시정지 상태일 수 있습니다)")
        return 1

    if not rows:
        print("X 수집 기록이 아예 없습니다 — 한 번도 성공하지 않았거나 테넌트가 없습니다")
        return 1

    print(f"테넌트 {len(rows)}곳 · 지연 기준 {stale_days:g}일\n")
    for r in sorted(rows, key=lambda x: (x.get("days_since") is None, -(float(x.get("days_since") or 0)))):
        print(_fmt(r))

    late = evaluate(rows, stale_days)
    if not late:
        print("\n정상 — 모두 기준 안입니다.")
        return 0

    print(f"\nX 갱신 지연 {len(late)}곳 — 맥 수집 작업을 확인해주세요.")
    print("   맥에서:  .venv/bin/python worker/sync_log.py")
    print("            launchctl list | grep mirrorball")
    print("            tail -40 runs/collect.out.log")
    webhook = os.environ.get("ALERT_WEBHOOK", "").strip()
    if webhook:
        notify(webhook, late, stale_days)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
