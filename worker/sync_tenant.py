"""살롱 1회 수집 → 담당(디자이너)별로 각 테넌트에 분리 업서트(멀티테넌트)."""

from __future__ import annotations

import re
import traceback
from collections import defaultdict
from datetime import date, timedelta

import mirrorball_crypto as mc
import scrape
import supa
from scrape import _derive

_PII_FIELDS = ("name", "birthday", "phone")


def _recompute_aggregates(tid: str) -> int:
    """전체 거래로 고객 집계 재계산 — 수집 창과 무관하게 방문수·주기·매출 lifetime 정확."""
    txs = supa.select_all("transactions", tid, "customer_id,date,amount_won")
    byc: dict = defaultdict(list)
    for t in txs:
        if t.get("customer_id") and t.get("date"):
            byc[t["customer_id"]].append((t["date"], t.get("amount_won") or 0))
    today_d = date.today()
    today = str(today_d)
    # VIP 판정용 최근 방문 횟수. 앱이 매번 전체 거래를 훑지 않도록 여기서 미리 센다.
    # 창은 3개 고정 — 설정(vip_recent_months)이 그중 하나를 고르므로 설정을 바꿔도 재수집 불필요.
    cut90, cut180, cut365 = (str(today_d - timedelta(days=n)) for n in (90, 180, 365))
    updates = []
    for cid, items in byc.items():
        dates = sorted({d for d, _ in items}, reverse=True)
        cycle, state = _derive(dates, len(dates), today)
        updates.append({
            "id": cid, "tenant_id": tid, "visit_count": len(dates),
            "first_visit": dates[-1] if dates else None,
            "last_visit": dates[0] if dates else None,
            "total_won": sum(a for _, a in items),
            "revisit_cycle_days": cycle, "revisit_state": state,
            "visits_90d": sum(1 for d in dates if d >= cut90),
            "visits_180d": sum(1 for d in dates if d >= cut180),
            "visits_365d": sum(1 for d in dates if d >= cut365),
        })
    supa.upsert("customers", updates, "id")
    return len(updates)


def _sync_one(tenant: dict, rows: list, reserve_rows: list, staff, reservations_ok: bool = True) -> dict:
    """살롱 원본을 이 디자이너(staff)로 필터·정규화해 이 테넌트에 업서트(각자 DEK)."""
    tid = tenant["id"]
    dek = mc.unwrap_dek(tenant["dek_wrapped"])
    data = scrape.normalize(rows, reserve_rows, staff, reservations_ok=reservations_ok)

    # 1) 고객: PII 암호화, 운영지표 평문. PII 필드는 항상 행에서 제거(없는 컬럼 400 방지).
    cust_rows = []
    for c in data.get("customers", []):
        c = dict(c)
        pii = {}
        for k in _PII_FIELDS:
            v = c.pop(k, None)
            if v is not None:
                pii[k] = v
        cust_rows.append({**c, "tenant_id": tid, "pii_enc": mc.encrypt_pii(pii, dek), "pii_kid": "v1"})
    supa.upsert("customers", cust_rows, "tenant_id,ext_id")

    # 2) ext_id → customer_id
    extmap = supa.get_customer_extmap(tid)
    tx = [
        {
            "tenant_id": tid,
            "customer_id": extmap.get(t.get("customer_ext")),
            "date": t["date"],
            "time": t.get("time"),
            "service": t.get("service"),
            "memo": t.get("memo"),
            "amount_won": t.get("amount_won", 0),
            "ext_id": t["ext_id"],
        }
        for t in data.get("transactions", [])
        if t.get("date")
    ]
    supa.upsert("transactions", tx, "tenant_id,ext_id")
    # 스테일 거래 정리(H2): 취소·보이드로 사라진 옛 행이 남아 매출·집계를 과대계상하지 않도록,
    # '이번에 실제 수집한 날짜 범위' 안에서만 현재 수집분에 없는 거래를 삭제. 범위 밖(창 밖
    # 과거 백필분)은 절대 건드리지 않는다 — 증분 수집(SYNC_DAYS)에서 과거 전멸 방지.
    tx_dates = sorted(t["date"] for t in tx if t.get("date"))
    if tx_dates:
        supa.delete_stale("transactions", tid, [t["ext_id"] for t in tx],
                          date_from=tx_dates[0], date_to=tx_dates[-1])

    # 3) 예약: 전화(→이름)로 고객 매칭. 전화/이름 맵(이 테넌트 고객 PII 복호화).
    by_phone: dict = {}
    by_name: dict = {}
    for c in supa.select_all("customers", tid, "id,pii_enc"):
        if not c.get("pii_enc"):
            continue
        try:
            p = mc.decrypt_pii(c["pii_enc"], dek)
        except Exception:
            continue
        ph = re.sub(r"\D", "", str(p.get("phone") or ""))
        if ph:
            by_phone.setdefault(ph, c["id"])
        nm = (p.get("name") or "").strip()
        if nm:
            by_name.setdefault(nm, c["id"])

    def _match(b: dict):
        return (
            extmap.get(b.get("customer_ext"))
            or (b.get("phone") and by_phone.get(b["phone"]))
            or (b.get("name") and by_name.get(b["name"]))
            or None
        )

    def _bpii(b: dict):
        pii = {k: b[k] for k in ("name", "phone") if b.get(k)}
        return mc.encrypt_pii(pii, dek) if pii else None

    bk = [
        {
            "tenant_id": tid,
            "customer_id": _match(b),
            "date": b["date"],
            "time": b.get("time"),
            "service": b.get("service"),
            "note": b.get("note"),
            "status": b.get("status"),
            "source": "handsos",
            "ext_id": b["ext_id"],
            "staff": b.get("staff"),
            "pii_enc": _bpii(b),
        }
        for b in data.get("bookings", [])
        if b.get("date")
    ]
    # 업서트 후 스테일 정리 — delete 를 먼저 하지 않아 insert/스키마 문제 시에도 예약이 비지 않음.
    # 예약 수확이 실패(reservations_ok=False)했으면 스테일 정리를 건너뛴다 — 빈 수집분으로
    # 기존 예약을 전량 삭제하는 사고 방지(H1). 정상 수확 시에만 allow_empty(진짜 0건 반영).
    res_ok = bool(data.get("reservations_ok", False))
    supa.upsert("bookings", bk, "tenant_id,ext_id")
    if res_ok:
        supa.delete_stale("bookings", tid, [b["ext_id"] for b in bk], allow_empty=True)

    recomputed = _recompute_aggregates(tid)
    return {"customers": len(cust_rows), "transactions": len(tx), "bookings": len(bk), "recomputed": recomputed}


def sync_salon(salon: dict) -> dict:
    """자격증명 보유 테넌트(살롱) 1회 수집 → designers 매핑대로 각 디자이너 테넌트에 분리 저장.
    designers 없으면 단일(자기 자신)로 동작(하위호환)."""
    cred_row = supa.get_credentials(salon["id"])
    if not cred_row:
        raise RuntimeError("pos_credentials 없음 — 자격증명 미등록")
    creds = mc.kek_decrypt_json(cred_row["enc_blob"])
    creds.setdefault("slug", salon.get("slug"))

    designers = creds.get("designers") or [
        {"staff": creds.get("staff"), "slug": salon.get("slug"), "name": salon.get("designer_name")}
    ]

    data = scrape.scrape_salon(creds)  # 살롱 1회 수집(로그인 1번)
    rows, reserve = data["rows"], data["reserve_rows"]
    res_ok = bool(data.get("reservations_ok", True))

    out: dict = {}
    for dz in designers:
        slug = dz.get("slug")
        target = supa.get_tenant_by_slug(slug) if slug else None
        if not target:
            print(f"  건너뜀(테넌트 없음): {slug} — onboard_designers.py 로 생성 필요")
            out[slug or "?"] = {"error": "no-tenant"}
            continue
        try:
            out[slug] = _sync_one(target, rows, reserve, dz.get("staff"), res_ok)
            print(f"  OK {slug}: {out[slug]}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            out[slug] = {"error": str(exc)}
    return out
