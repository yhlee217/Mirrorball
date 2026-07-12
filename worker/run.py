"""워커 엔트리포인트 — queued sync_jobs 를 집어 처리(1회 실행). Fly 스케줄/cron 이 주기 호출."""

from __future__ import annotations

import datetime as dt
import traceback

import supa
from sync_tenant import sync_tenant


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _preflight() -> None:
    """필수 시크릿 확인 — 없으면 트레이스백 대신 원인 한 줄로 즉시 종료."""
    import os

    url_ok = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    missing = ([] if url_ok else ["SUPABASE_URL"]) + [
        k for k in ("SUPABASE_SERVICE_ROLE_KEY", "MIRRORBALL_KEK") if not os.environ.get(k)
    ]
    if missing:
        raise SystemExit(
            "❌ 필수 시크릿 미설정: " + ", ".join(missing)
            + "\n   GitHub 리포 → Settings → Secrets and variables → Actions 에 등록하세요."
            + "\n   값은 web/.env.local 의 같은 키에서 복사(SUPABASE_URL = NEXT_PUBLIC_SUPABASE_URL)."
        )


def main() -> None:
    jobs = supa.claim_jobs(limit=5)
    if not jobs:
        print("queued 잡 없음")
        return

    for job in jobs:
        supa.update_job(job["id"], status="running", started_at=_now())
        try:
            tenant = supa.get_tenant(job["tenant_id"])
            if not tenant:
                raise RuntimeError("tenant 없음")
            stats = sync_tenant(tenant)
            supa.update_job(job["id"], status="ok", finished_at=_now(), stats=stats)
            print("OK", job["tenant_id"], stats)
        except Exception as exc:  # noqa: BLE001
            supa.update_job(job["id"], status="error", error=str(exc), finished_at=_now())
            traceback.print_exc()


def sync_all() -> None:
    """자격증명 등록된 전 테넌트를 큐 없이 즉시 동기화(무료 GitHub Actions/cron용)."""
    try:
        tenants = supa.list_credentialed_tenants()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"❌ Supabase 접근 실패(시크릿 값·네트워크 확인): {exc}")
    if not tenants:
        print("자격증명 등록된 테넌트 없음 — 정상 종료(수집 대상 없음)")
        return
    ok = 0
    for t in tenants:
        try:
            stats = sync_tenant(t)
            print("OK", t.get("slug"), stats)
            ok += 1
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    if ok == 0:
        raise SystemExit(f"❌ 전 테넌트 수집 실패({len(tenants)}개) — 위 traceback 참고")
    print(f"완료: {ok}/{len(tenants)} 성공")


def loop() -> None:
    import os
    import time

    interval = int(os.environ.get("POLL_SECONDS", "300"))
    print(f"워커 폴링 시작 · 간격 {interval}s")
    while True:
        try:
            main()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(interval)


if __name__ == "__main__":
    import os

    _preflight()
    if os.environ.get("SYNC_ALL"):
        sync_all()      # 전 테넌트 1회(무료 GitHub Actions)
    elif os.environ.get("RUN_ONCE"):
        main()          # queued 잡 1회
    else:
        loop()          # 상시 폴링
