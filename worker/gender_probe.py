"""성별 추정이 실제로 쓸 만한지 분포를 재본다 — 읽기 전용, AI 미사용.

'남자컷/여자컷으로 성별 통계를 낼 수 있을까'를 추측으로 정하지 않으려고 만든다.
대행결제(엄마가 아들 결제, 부부 대행)가 얼마나 섞여 있는지가 설계를 가른다.

사용:
    .venv/bin/python worker/gender_probe.py
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
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

import supa      # noqa: E402
import gender    # noqa: E402
import txkind    # noqa: E402


def main() -> int:
    tenants = supa._get("/tenants", {"select": "id,slug", "order": "slug"})
    for t in tenants:
        tid, slug = t["id"], t.get("slug") or t["id"][:8]
        txs = supa.select_all("transactions", tid, "customer_id,service,kind")
        custs = {c["id"]: c for c in supa.select_all("customers", tid, "id,family_ext_id")}

        by_cust: dict = defaultdict(list)
        clue_tx = 0
        for r in txs:
            if not r.get("customer_id"):
                continue
            if (r.get("kind") or txkind.classify(r.get("service"))) != "service":
                continue
            svc = r.get("service")
            by_cust[r["customer_id"]].append(svc)
            if gender.service_gender(svc):
                clue_tx += 1

        total_tx = sum(len(v) for v in by_cust.values())
        buckets = Counter()
        mixed_with_family = 0
        kid_n = 0
        for cid, svcs in by_cust.items():
            r = gender.infer(svcs)
            if r["kid"]:
                kid_n += 1
            if r["mixed"]:
                buckets["혼재(대행의심)"] += 1
                if custs.get(cid, {}).get("family_ext_id"):
                    mixed_with_family += 1
            elif r["gender"] == "M":
                buckets["남성"] += 1
            elif r["gender"] == "F":
                buckets["여성"] += 1
            else:
                buckets["단서없음"] += 1

        n = len(by_cust)
        print(f"\n[{slug}] 고객 {n}명 · 시술거래 {total_tx}건")
        print(f"  성별 단서가 있는 거래: {clue_tx}건 ({clue_tx * 100 // max(total_tx, 1)}%)")
        for k in ("남성", "여성", "혼재(대행의심)", "단서없음"):
            v = buckets.get(k, 0)
            print(f"    {k:<14} {v:>5}명 ({v * 100 // max(n, 1)}%)")
        print(f"  혼재 중 가족 연결 있음: {mixed_with_family}명 (가족이면 대행 가능성 높음)")
        print(f"  아동·주니어 시술 이력: {kid_n}명")
    print("\n→ '혼재'와 '단서없음'이 크면 성별 통계는 '판정된 고객만' 기준으로 내야 정직하다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
