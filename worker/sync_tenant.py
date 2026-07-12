"""한 테넌트 동기화: 자격증명 복호화 → 스크레이프 → PII 암호화 → Supabase 업서트."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

import mirrorball_crypto as mc
import supa
from scrape import _derive, scrape_tenant

_PII_FIELDS = ("name", "birthday", "phone")


def _recompute_aggregates(tid: str) -> int:
    """전체 거래로 고객 집계 재계산 — 수집 창과 무관하게 방문수·주기·매출 lifetime 정확."""
    txs = supa.select_all("transactions", tid, "customer_id,date,amount_won")
    byc: dict = defaultdict(list)
    for t in txs:
        if t.get("customer_id") and t.get("date"):
            byc[t["customer_id"]].append((t["date"], t.get("amount_won") or 0))
    today = str(date.today())
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
        })
    supa.upsert("customers", updates, "id")
    return len(updates)


def sync_tenant(tenant: dict) -> dict:
    tid = tenant["id"]
    dek = mc.unwrap_dek(tenant["dek_wrapped"])

    cred_row = supa.get_credentials(tid)
    if not cred_row:
        raise RuntimeError("pos_credentials 없음 — 자격증명 미등록")
    creds = mc.kek_decrypt_json(cred_row["enc_blob"])
    creds.setdefault("slug", tenant.get("slug"))

    data = scrape_tenant(creds, cred_row.get("session_cookie"))

    # 1) 고객: PII 암호화, 운영지표 평문
    cust_rows = []
    for c in data.get("customers", []):
        c = dict(c)
        # PII 필드(name/birthday/phone)는 값 유무와 무관하게 항상 행에서 제거 —
        # customers 엔 평문 PII 컬럼이 없고(pii_enc 로 암호화), None 이 남으면 400(PGRST204).
        pii = {}
        for k in _PII_FIELDS:
            v = c.pop(k, None)
            if v is not None:
                pii[k] = v
        cust_rows.append({**c, "tenant_id": tid, "pii_enc": mc.encrypt_pii(pii, dek), "pii_kid": "v1"})
    supa.upsert("customers", cust_rows, "tenant_id,ext_id")

    # 2) ext_id → customer_id 매핑(거래·예약 연결)
    extmap = supa.get_customer_extmap(tid)

    tx = [
        {
            "tenant_id": tid,
            "customer_id": extmap.get(t.get("customer_ext")),
            "date": t["date"],
            "service": t.get("service"),
            "amount_won": t.get("amount_won", 0),
            "ext_id": t["ext_id"],
        }
        for t in data.get("transactions", [])
        if t.get("date")
    ]
    supa.upsert("transactions", tx, "tenant_id,ext_id")

    # 3) 예약: 전량 새로고침(중복·스테일 방지)
    # 예약행엔 고객번호가 없어 전화(→이름) 로 고객 매칭. 전화/이름 맵 구성(PII 복호화).
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
            "source": "handsos",
            "ext_id": b["ext_id"],
            "pii_enc": _bpii(b),  # 예약자 이름/전화(매칭 안 돼도 표시용)
        }
        for b in data.get("bookings", [])
        if b.get("date")
    ]
    # 업서트 후 스테일 정리 — delete 를 먼저 하지 않아 insert/스키마 문제 시에도 예약이 비지 않음.
    supa.upsert("bookings", bk, "tenant_id,ext_id")
    supa.delete_stale("bookings", tid, [b["ext_id"] for b in bk])

    # TODO: 갱신된 session_cookie 를 pos_credentials 에 암호화 저장(재로그인 회피)

    recomputed = _recompute_aggregates(tid)

    return {"customers": len(cust_rows), "transactions": len(tx), "bookings": len(bk), "recomputed": recomputed}
