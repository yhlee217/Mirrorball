"""HandSOS 스크레이프 — v1 handsos_sync.harvest_store 재사용 + 워커용 정규화.

컨테이너에 리포의 scripts/handsos_sync.py, scripts/handsos_harvest.js,
scripts/handsos_selectors.yaml, handsos_reserve.py 가 있어야 한다(Dockerfile 참고).
브라우저 자동화(로그인·saleList 프레임 수확·예약)는 검증된 v1을 그대로 호출하고,
여기서는 (1) 자격증명→store 구성 (2) 수확 행(9열 dict)→우리 스키마 정규화 만 담당.

반환: {"customers":[{ext_id,name,phone?,visit_count,first_visit,last_visit,total_won,revisit_cycle_days,revisit_state}],
       "transactions":[{ext_id,customer_ext,date,service,amount_won}],
       "bookings":[{ext_id,customer_ext,date,time,service}]}
PII(name/phone)는 평문 반환 → sync_tenant 가 DEK로 암호화.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))


def _norm_date(v) -> str | None:
    if not v:
        return None
    m = re.search(r"(\d{2,4})\D(\d{1,2})\D(\d{1,2})", str(v))
    if not m:
        return None
    y, mo, d = m.groups()
    if len(y) == 2:
        y = "20" + y
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def _won(v) -> int:
    if v is None:
        return 0
    m = re.findall(r"-?\d+", str(v).replace(",", ""))
    return int("".join(m)) if m else 0


def _derive(dates_desc: list[str], visits: int, today: str):
    last = dates_desc[0] if dates_desc else None
    cycle = None
    if len(dates_desc) >= 2:
        ds = [datetime.fromisoformat(x) for x in dates_desc]
        gaps = sorted((ds[i] - ds[i + 1]).days for i in range(len(ds) - 1))
        m = gaps[len(gaps) // 2]
        if m > 0:
            cycle = m
    state = None
    if visits <= 1:
        state = "new"
    elif last:
        days = (datetime.fromisoformat(today) - datetime.fromisoformat(last)).days
        cyc = cycle or 42
        if days > cyc * 1.6:
            state = "overdue"
        elif days >= cyc:
            state = "due"
    return cycle, state


def normalize(rows: list[dict], reserve_rows: list[dict], staff: str | None = None) -> dict:
    """수확 행(한글 9열 dict) + 예약 행 → 스키마. 고객번호로 집계."""
    custs: dict[str, dict] = {}
    raw_tx: list[dict] = []
    today = str(date.today())

    for r in rows:
        if staff and r.get("담당") and staff not in str(r.get("담당")):
            continue  # 테넌트=디자이너: 자기 담당 행만(라벨 상이 시 secrets 매핑으로 보정)
        ext = (r.get("고객번호") or "").strip() or (r.get("고객명") or "").strip()
        if not ext:
            continue
        name = (r.get("고객명") or "").strip()
        d = _norm_date(r.get("날짜"))
        won = _won(r.get("결제액"))
        svc = (r.get("상세메뉴") or "").strip() or None
        c = custs.setdefault(ext, {"ext_id": ext, "name": name, "phone": (r.get("전화번호") or "").strip() or None, "dates": set(), "total_won": 0})
        if name and not c["name"]:
            c["name"] = name
        if d:
            c["dates"].add(d)
        c["total_won"] += won
        raw_tx.append({"customer_ext": ext, "date": d, "service": svc, "amount_won": won})

    customers = []
    for ext, c in custs.items():
        dates = sorted(c["dates"], reverse=True)
        cycle, state = _derive(dates, len(dates), today)
        customers.append({
            "ext_id": ext, "name": c["name"] or None, "phone": c["phone"],
            "visit_count": len(dates), "first_visit": dates[-1] if dates else None,
            "last_visit": dates[0] if dates else None, "total_won": c["total_won"],
            "revisit_cycle_days": cycle, "revisit_state": state,
        })

    seq: dict[str, int] = defaultdict(int)
    transactions = []
    for t in raw_tx:
        i = seq[t["customer_ext"]]
        seq[t["customer_ext"]] += 1
        transactions.append({"ext_id": f"{t['customer_ext']}-{i}", **t})

    bookings = []
    for i, b in enumerate(reserve_rows or []):
        bookings.append({
            "ext_id": f"B{i}",
            "customer_ext": (b.get("고객번호") or b.get("custno") or b.get("customer_ext")),
            "date": _norm_date(b.get("날짜") or b.get("date")),
            "time": b.get("시간") or b.get("time"),
            "service": b.get("메뉴") or b.get("service"),
        })

    return {"customers": customers, "transactions": transactions, "bookings": bookings}


def scrape_tenant(creds: dict, session_cookie: str | None = None) -> dict:
    """v1 harvest_store/harvest_reservations 재사용 → normalize."""
    import handsos_sync as hs  # noqa: 지연 import(playwright 등)

    slug = creds.get("slug") or "tenant"
    staff = creds.get("staff")
    store = {
        "slug": slug,
        "staff": staff,
        "company_code": creds.get("company") or creds.get("company_code") or "",
        "username": creds.get("id"),
        "password": creds.get("pw"),
        "report": {"date_range_days": int(creds.get("days", 7))},
        "collect_reservations": True,
    }
    hs.apply_overrides(store)  # secrets/{slug}.selectors.yaml 오버라이드(있으면)

    res = hs.harvest_store(store)
    rows = res.get("rows") or []
    if not rows:
        raise RuntimeError(f"harvest 실패: {res.get('error') or '0행'}")

    reserve_rows = []
    try:
        rres = hs.harvest_reservations(store)
        reserve_rows = rres.get("parsed") or []
    except Exception:
        reserve_rows = []

    return normalize(rows, reserve_rows, staff)
