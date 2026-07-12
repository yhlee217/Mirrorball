"""테넌트 데이터 초기화(bookings→transactions→customers). 워커 단일소스 재구축 전용.

사용:      .venv/bin/python worker/wipe_tenant.py <slug>            # 미리보기(삭제 안 함)
     CONFIRM=1 .venv/bin/python worker/wipe_tenant.py <slug>       # 실제 삭제
시크릿은 web/.env.local 에서 자동 로드. profiles/pos_credentials/tenant 는 보존.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    p = ROOT / "web" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]


_load_env()

import supa  # noqa: E402


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else None
    if not slug:
        raise SystemExit("사용법: [CONFIRM=1] .venv/bin/python worker/wipe_tenant.py <slug>")
    t = supa.get_tenant_by_slug(slug)
    if not t:
        raise SystemExit(f"tenant 없음: {slug}")
    tid = t["id"]

    counts = {tbl: len(supa.select_all(tbl, tid, "id")) for tbl in ("customers", "transactions", "bookings")}
    print(f"[{slug}] 현재: customers={counts['customers']} transactions={counts['transactions']} bookings={counts['bookings']}")

    if not os.environ.get("CONFIRM"):
        print("미리보기입니다. 실제 삭제하려면 CONFIRM=1 을 붙여 다시 실행하세요.")
        return 0

    for tbl in ("bookings", "transactions", "customers"):  # 자식→부모 순
        supa.delete(tbl, tid)
        print(f"삭제 완료: {tbl}")
    print("초기화 완료. 이제 SYNC_DAYS=1825 FORCE=1 bash worker/run_mac.sh 로 전체이력 재수집하세요(365일씩 분할).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
