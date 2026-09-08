"""고객 집계 재계산만 단독 실행 — 수집(스크래핑) 없이.

분류·매출 정의가 바뀌면 과거 데이터에도 소급해야 하는데, 그것 때문에 HandSOS 를
다시 긁을 이유는 없다. DB 안의 거래만 다시 훑어 방문수·매출·선불잔액을 새로 낸다.
AI 도 쓰지 않는다(순수 산술).

사용:
    .venv/bin/python worker/recompute.py
"""

from __future__ import annotations

import os
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
from sync_tenant import _recompute_aggregates  # noqa: E402


def main() -> int:
    try:
        supa._get("/transactions", {"select": "id,kind,covered_won", "limit": "1"})
        supa._get("/customers", {"select": "id,prepaid_balance", "limit": "1"})
    except RuntimeError as exc:
        if "42703" not in str(exc) and "does not exist" not in str(exc):
            raise
        print("❌ 마이그레이션 0019 가 아직 적용되지 않았습니다.")
        print("   Supabase SQL Editor 에서 아래 파일 내용을 실행한 뒤 다시 돌리세요:")
        print("   supabase/migrations/0019_transaction_kind.sql")
        print("\n   (이미 실행했는데도 이 메시지가 나오면 스키마 캐시 갱신)")
        print("   notify pgrst, 'reload schema';")
        return 1

    tenants = supa._get("/tenants", {"select": "id,slug", "order": "slug"})
    total = 0
    for t in tenants:
        slug = t.get("slug") or t["id"][:8]
        n = _recompute_aggregates(t["id"])
        total += n
        print(f"[{slug}] 고객 {n}명 재계산")
    print(f"완료: {total}명")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
