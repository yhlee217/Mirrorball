"""고아 거래(customer_id null) 재연결 + 고객 집계 재계산 — 재수집 없이 사후 복구.

원인: get_customer_extmap 이 1000행 상한에 걸려 1000번째 이후 고객이 맵에서 빠짐 → 그 거래가 고아.
수정(supa.get_customer_extmap 페이지네이션) 반영 후, 이 스크립트로 기존 고아만 재연결.

사용: .venv/bin/python worker/relink.py <slug>
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
from sync_tenant import _recompute_aggregates  # noqa: E402


def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else None
    if not slug:
        raise SystemExit("사용법: .venv/bin/python worker/relink.py <slug>")
    t = supa.get_tenant_by_slug(slug)
    if not t:
        raise SystemExit(f"tenant 없음: {slug}")
    tid = t["id"]

    extmap = supa.get_customer_extmap(tid)  # 페이지네이션 수정 반영 → 전 고객
    print(f"고객 맵 {len(extmap)}명")

    txs = supa.select_all("transactions", tid, "ext_id,customer_id")
    fixes = []
    for x in txs:
        if not x.get("customer_id"):
            custno = (x.get("ext_id") or "").split("-", 1)[0]  # ext_id = 고객번호-날짜-순번
            cid = extmap.get(custno)
            if cid:
                fixes.append({"tenant_id": tid, "ext_id": x["ext_id"], "customer_id": cid})
    print(f"고아 거래 재연결 대상 {len(fixes)}건")
    for i in range(0, len(fixes), 500):
        supa.upsert("transactions", fixes[i : i + 500], "tenant_id,ext_id")

    n = _recompute_aggregates(tid)
    print(f"집계 재계산 {n}명 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
