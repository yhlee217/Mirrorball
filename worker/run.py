"""워커 엔트리포인트 — queued sync_jobs 를 집어 처리(1회 실행). Fly 스케줄/cron 이 주기 호출."""

from __future__ import annotations

import datetime as dt
import traceback

import supa
from sync_tenant import sync_tenant


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


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
    tenants = supa.list_credentialed_tenants()
    if not tenants:
        print("자격증명 등록된 테넌트 없음")
        return
    for t in tenants:
        try:
            stats = sync_tenant(t)
            print("OK", t.get("slug"), stats)
        except Exception:  # noqa: BLE001
            traceback.print_exc()


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

    if os.environ.get("SYNC_ALL"):
        sync_all()      # 전 테넌트 1회(무료 GitHub Actions)
    elif os.environ.get("RUN_ONCE"):
        main()          # queued 잡 1회
    else:
        loop()          # 상시 폴링
