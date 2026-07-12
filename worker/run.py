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


if __name__ == "__main__":
    main()
