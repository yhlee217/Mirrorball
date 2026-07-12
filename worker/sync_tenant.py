"""한 테넌트 동기화: 자격증명 복호화 → 스크레이프 → PII 암호화 → Supabase 업서트."""

from __future__ import annotations

import mirrorball_crypto as mc
import supa
from scrape import scrape_tenant

_PII_FIELDS = ("name", "birthday", "phone")


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
    bk = [
        {
            "tenant_id": tid,
            "customer_id": extmap.get(b.get("customer_ext")),
            "date": b["date"],
            "time": b.get("time"),
            "service": b.get("service"),
            "source": "handsos",
            "ext_id": b["ext_id"],
        }
        for b in data.get("bookings", [])
        if b.get("date")
    ]
    supa.delete("bookings", tid)
    supa.insert("bookings", bk)

    # TODO: 갱신된 session_cookie 를 pos_credentials 에 암호화 저장(재로그인 회피)

    return {"customers": len(cust_rows), "transactions": len(tx), "bookings": len(bk)}
