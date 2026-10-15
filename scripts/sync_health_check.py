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

운영 기록(0023 ops_health, 개선 계획 v5) — 같은 길로 함께 본다
    · 앱 데이터 백업(worker/backup.py, 맥 일요일) — 매장별 마지막 백업이 8일 넘으면 실패
    · 화면 오류(app/error.tsx 가 기록) — 지난 24시간 매장별 ERROR_LIMIT 건 이상이면 실패
    BACKUP_REQUIRED_SINCE 전에는 0023 미적용·백업 기록 없음을 경고만 한다(맥에 새 코드가 깔리고 첫
    일요일이 지나기 전) — 그 뒤로는 실패다. 안 그러면 '설치를 안 했다'를 영원히 모른다.

화면 속도 · 매장별 사용(0024 ops_speed · ops_usage, 개선 계획 v7) — 출력만 하고 실패로 만들지 않는다
    · 화면별 보통 · 느린 때(지난 7일, 폰에서 잰 '누른 순간 → 내용이 뜬 순간')
    · 매장별 화면 연 수 · 연락한 손님 수 · 마지막 사용 — 다음 개선을 정하는 숫자(맥 점검 없이)
    · 0025 뒤(개선 계획 v10 P0): 화면 수는 디자이너 것만(운영자 폰은 따로) · 그중 홈 화면 앱으로 연 비율 · 기록 시작
    · 0026 뒤(개선 계획 v14 P0): CSP(보고만) 어긋남 — 규칙 · 출처별 건수(출력만)

사용:
    SUPABASE_URL=... SUPABASE_ANON_KEY=... python3 scripts/sync_health_check.py
    STALE_DAYS=8    지연 판정 기준(기본 8)
    BACKUP_DAYS=8   백업 지연 기준(기본 8)
    ERROR_LIMIT=5   매장별 24시간 화면 오류 기준(기본 5)
    BACKUP_REQUIRED_SINCE=YYYY-MM-DD   이 날부터 백업 기록이 없으면 실패
    ALERT_WEBHOOK   (선택) 설정하면 지연 시 JSON 을 POST 한다
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

# 수집은 일요일 1회다. 정상이면 '마지막 성공으로부터'는 최대 7일(일요일 수집 직전)이므로
# 8 이상은 예정된 일요일이 통째로 빈 것이다. web/lib/sync.ts 의 isSyncStale 과 같은 기준.
DEFAULT_STALE_DAYS = 8
DEFAULT_BACKUP_DAYS = 8      # 백업도 일요일 1회 — 수집과 같은 이유로 8
DEFAULT_ERROR_LIMIT = 5      # 디자이너 한 명이 하루에 오류 화면을 다섯 번 보면 쓰기 어렵다
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


def evaluate_ops(rows: list[dict], now: dt.datetime, backup_days: float, error_limit: int,
                 required: bool) -> tuple[list[str], list[str]]:
    """(실패, 경고). 네트워크와 분리해 테스트한다. rows = ops_health() 결과."""
    bad, warn = [], []
    for r in rows:
        slug = r.get("slug", "?")
        last = r.get("last_backup")
        if last is None:
            (bad if required else warn).append(f"{slug}: 백업 기록 없음")
        else:
            age = (now - dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))).total_seconds() / 86400
            if age >= backup_days:
                bad.append(f"{slug}: 마지막 백업 {age:.1f}일 전")
        n = int(r.get("errors_24h") or 0)
        if n >= error_limit:
            bad.append(f"{slug}: 지난 24시간 화면 오류 {n}건")
    return bad, warn


def fmt_speed(rows: list[dict]) -> list[str]:
    """화면별 속도(0024 ops_speed, 개선 계획 v7) — 기다린 화면의 보통(중간값) · 느린 때(10번 중 가장 느린 1번).
    받아 둔 화면을 바로 보여준 것은 횟수만 — 섞으면 서버가 느린 것이 가려진다."""
    out = []
    for r in rows:
        p50, p90 = r.get("p50_ms"), r.get("p90_ms")
        instant = int(r.get("instant") or 0)
        waited = int(r.get("opened") or 0) - instant
        speed = (f"보통 {p50 / 1000:.1f}초 · 느린 때 {p90 / 1000:.1f}초 · {waited}번"
                 if p50 is not None and p90 is not None else "기다린 적 없음")
        out.append(f"  {str(r.get('screen') or '?'):20s} {speed}" + (f" (바로 {instant}번)" if instant else ""))
    return out


KST = dt.timezone(dt.timedelta(hours=9))


def _when(ts: object) -> dt.datetime:
    return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def fmt_usage(rows: list[dict], now: dt.datetime) -> list[str]:
    """매장별 사용(ops_usage) — 화면 연 수 · 연락한 손님 수(지난 7일) · 마지막으로 앱을 쓴 때. 숫자만.

    0025(개선 계획 v10 P0) 뒤엔 화면 수가 디자이너 것만이다 — 운영자 폰은 따로 세고(op_7d), 그중 홈 화면 앱으로
    연 비율(app_7d)을 붙이고, 맨 위에 기록 시작(since)을 찍는다('0번'이 며칠 기준인지). 칸이 없으면(0024) 예전 그대로.
    """
    out = []
    marked = any("op_7d" in r for r in rows)
    since = next((r["since"] for r in rows if r.get("since")), None)
    if since:
        out.append(f"  화면 기록 {_when(since).astimezone(KST):%m.%d %H:%M}부터 · 운영자 폰은 따로 셈")
    elif marked:
        out.append("  화면 기록 — 새 앱의 기록이 아직 없음(운영자 폰은 따로 셈)")
    for r in rows:
        last = r.get("last_seen")
        if last:
            days = (now - _when(last)).total_seconds() / 86400
            seen = "오늘" if days < 1 else f"{int(days)}일 전"
        else:
            seen = "기록 없음"
        slug = str(r.get("slug") or "?")
        screens = int(r.get("screens_7d") or 0)
        contacts = int(r.get("contacts_7d") or 0)
        if "op_7d" not in r:  # 0024 — 매장 단위(운영자 폰이 섞인다)
            out.append(f"  {slug:12s} 화면 {screens}번 · 연락 {contacts}명 · 마지막 사용 {seen}")
            continue
        app, op = int(r.get("app_7d") or 0), int(r.get("op_7d") or 0)
        share = f"(앱 {round(app * 100 / screens)}%)" if screens else ""
        out.append(f"  {slug:12s} 디자이너 화면 {screens}번{share} · 연락 {contacts}명 · 마지막 사용 {seen}"
                   + (f" · 운영자 폰 {op}번" if op else ""))
    return out


def fmt_csp(rows: list[dict]) -> list[str]:
    """CSP(보고만) 어긋남(0026 ops_csp, 개선 계획 v14 P0) — 지난 7일 규칙 · 출처별 건수. 출처와 숫자만."""
    if not rows:
        return ["  어긋남 없음"]
    return [f"  {str(r.get('directive') or '?'):16s} {str(r.get('blocked') or '?'):40s} {int(r.get('n') or 0)}번" for r in rows]


def report_csp(url: str, key: str) -> None:
    """CSP 어긋남(0026) — 보고만 하는 한 주 동안 무엇이 막힐 뻔했나. 실패로 만들지 않는다. 0026 전이면 한 줄만."""
    try:
        rows = fetch(url, key, "ops_csp")
    except urllib.error.HTTPError as exc:
        print(f"\nCSP(보고만) — 조회 실패 HTTP {exc.code} — 0026_csp_reports.sql 을 적용했는지 확인하세요")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"\nCSP(보고만) — 조회 실패: {exc}")
        return
    print("\nCSP(보고만) — 지난 7일 어긋남(규칙 · 출처 · 건수)")
    print("\n".join(fmt_csp(rows)))


def report_speed_usage(url: str, key: str) -> None:
    """화면 속도 · 매장별 사용(0024) — 알려 주기만 하고 실패로 만들지 않는다. 다음 개선(v7 P1 · P2)을 정하는 숫자."""
    try:
        speed = fetch(url, key, "ops_speed")
        usage = fetch(url, key, "ops_usage")
    except urllib.error.HTTPError as exc:
        print(f"\n! 화면 속도 · 사용 수 조회 실패 HTTP {exc.code} — 0024_speed_usage.sql 을 적용했는지 확인하세요")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"\n! 화면 속도 · 사용 수 조회 실패: {exc}")
        return
    print("\n화면 속도 — 지난 7일 (누른 순간 → 내용이 뜬 순간, 받아 둔 화면은 '바로')")
    print("\n".join(fmt_speed(speed)) if speed else "  아직 기록 없음")
    print("\n매장별 사용 — 지난 7일")
    print("\n".join(fmt_usage(usage, dt.datetime.now(dt.timezone.utc))) if usage else "  아직 기록 없음")


def fetch(url: str, key: str, fn: str = "sync_health") -> list[dict]:
    req = urllib.request.Request(
        url.rstrip("/") + f"/rest/v1/rpc/{fn}",
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
    ops_bad = check_ops(url, key)
    report_speed_usage(url, key)
    report_csp(url, key)
    if not late and not ops_bad:
        print("\n정상 — 모두 기준 안입니다.")
        return 0

    if late:
        print(f"\nX 갱신 지연 {len(late)}곳 — 맥 수집 작업을 확인해주세요.")
        print("   맥에서:  .venv/bin/python worker/sync_log.py")
        print("            launchctl list | grep mirrorball")
        print("            tail -40 runs/collect.out.log")
        webhook = os.environ.get("ALERT_WEBHOOK", "").strip()
        if webhook:
            notify(webhook, late, stale_days)
    return 1


def check_ops(url: str, key: str) -> list[str]:
    """백업·화면 오류(0023 ops_health). 실패 줄을 돌려준다 — 없으면 정상."""
    since = os.environ.get("BACKUP_REQUIRED_SINCE", "").strip()
    required = bool(since) and dt.date.today().isoformat() >= since
    try:
        rows = fetch(url, key, "ops_health")
    except urllib.error.HTTPError as exc:
        msg = f"운영 기록 조회 실패 HTTP {exc.code} — 0023_ops_events.sql 을 적용했는지 확인하세요"
        if required:
            print(f"\nX {msg}")
            return [msg]
        print(f"\n! {msg} (아직 경고만 — {since or '기한 미정'}부터 실패)")
        return []
    except Exception as exc:  # noqa: BLE001
        print(f"\n! 운영 기록 조회 실패: {exc}")
        return []
    bad, warn = evaluate_ops(
        rows, dt.datetime.now(dt.timezone.utc),
        float(os.environ.get("BACKUP_DAYS") or DEFAULT_BACKUP_DAYS),
        int(os.environ.get("ERROR_LIMIT") or DEFAULT_ERROR_LIMIT),
        required,
    )
    for w in warn:
        print(f"! {w} (아직 경고만 — {since or '기한 미정'}부터 실패)")
    if bad:
        print("\nX 운영 기록 — " + " · ".join(bad))
        print("   백업: 맥에서 .venv/bin/python worker/backup.py  (일요일 수집 직후 자동)")
        print("   화면 오류: Cloudflare 로그에서 같은 시각 오류를 찾아보세요(기록엔 화면 경로·오류 번호만 있다)")
    else:
        print("\n운영 기록 정상 — 백업·화면 오류 기준 안")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
