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
        txs = supa.select_all("transactions", tid, "customer_id,service,date,memo,kind")
        try:
            custs = {c["id"]: c for c in supa.select_all("customers", tid, "id,ext_id,family_ext_id,gender")}
            db_set = sum(1 for c in custs.values() if c.get("gender"))
        except RuntimeError:
            custs = {c["id"]: c for c in supa.select_all("customers", tid, "id,ext_id,family_ext_id")}
            db_set = None

        # 앱과 같은 기준: 고객번호(숫자)를 가진 실제 고객만. '손님' 워크인은 관리 대상이 아니다.
        real = {cid for cid, c in custs.items() if str(c.get("ext_id") or "").isdigit()}
        by_cust: dict = defaultdict(list)
        clue_tx = 0
        for r in txs:
            if not r.get("customer_id") or r["customer_id"] not in real:
                continue
            if (r.get("kind") or txkind.classify(r.get("service"))) != "service":
                continue
            by_cust[r["customer_id"]].append(
                {"service": r.get("service"), "date": r.get("date"), "memo": r.get("memo")})
            if gender.service_gender(r.get("service")):
                clue_tx += 1

        total_tx = sum(len(v) for v in by_cust.values())
        buckets = Counter()
        howto = Counter()
        proxy_with_family = 0
        kid_self = 0
        for cid, rows in by_cust.items():
            r = gender.infer(rows)
            if r["age_band"] == "kid":
                kid_self += 1
            if r["proxy"]:
                buckets["판정불가(대행)"] += 1
                if custs.get(cid, {}).get("family_ext_id"):
                    proxy_with_family += 1
            elif r["gender"] == "M":
                buckets["남성"] += 1
                howto[r["resolved_by"]] += 1
            elif r["gender"] == "F":
                buckets["여성"] += 1
                howto[r["resolved_by"]] += 1
            else:
                buckets["단서없음"] += 1

        n = len(by_cust)
        print(f"\n[{slug}] 고객 {n}명 · 시술거래 {total_tx}건")
        print(f"  성별 단서가 있는 거래: {clue_tx}건 ({clue_tx * 100 // max(total_tx, 1)}%)")
        for k in ("남성", "여성", "판정불가(대행)", "단서없음"):
            v = buckets.get(k, 0)
            print(f"    {k:<14} {v:>5}명 ({v * 100 // max(n, 1)}%)")
        print(f"  판정 근거: 시술명 {howto.get('service', 0)}명 · "
              f"메모(가족 귀속) {howto.get('memo-family', 0)}명 · 메모(배우자) {howto.get('memo-spouse', 0)}명")
        print(f"  판정불가 중 가족 연결 있음: {proxy_with_family}명")
        print(f"  본인이 아동·학생으로 보임: {kid_self}명")
        if db_set is None:
            print("  DB customers.gender: 컬럼 없음 (0020 미적용) → 화면은 전부 '미상'으로 보인다")
        else:
            print(f"  DB customers.gender 채워진 고객: {db_set}명"
                  + ("  ⚠ 0이면 recompute.py 를 아직 안 돌린 것 — 화면은 전부 '미상'" if db_set == 0 else ""))

        # 왜 미상인가 — 단서가 하나도 없는 고객들이 실제로 무슨 시술을 받았는지 본다.
        # 여기 상위 메뉴에 성별이 드러나 있으면 규칙을 넓혀 미상을 줄일 수 있다.
        noclue = Counter()
        noclue_cust = 0
        for cid, rows in by_cust.items():
            if any(gender.service_gender(r.get("service")) for r in rows):
                continue
            noclue_cust += 1
            for r in rows:
                sv = (r.get("service") or "").strip()
                if sv:
                    noclue[sv] += 1
        if noclue:
            print(f"  ── 단서 0 인 고객 {noclue_cust}명이 받은 시술 상위 20 ──")
            for name, cnt in noclue.most_common(20):
                print(f"     {cnt:>5}회  {name}")
    print("\n→ 메모로 갈린 인원이 많으면 추정이 값을 한다. '판정불가'와 '단서없음'만 통계에서 뺀다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
