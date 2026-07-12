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

    data = scrape_tenant(creds, cred_row.get("session_cookie"))

    # 고객: PII 암호화(pii_enc), 운영지표 평문
    cust_rows = []
    for c in data.get("customers", []):
        c = dict(c)
        pii = {k: c.pop(k) for k in _PII_FIELDS if k in c}
        cust_rows.append({**c, "tenant_id": tid, "pii_enc": mc.encrypt_pii(pii, dek), "pii_kid": "v1"})
    supa.upsert("customers", cust_rows, "tenant_id,ext_id")

    supa.upsert(
        "transactions",
        [{**t, "tenant_id": tid} for t in data.get("transactions", [])],
        "tenant_id,ext_id",
    )
    supa.upsert(
        "bookings",
        [{**b, "tenant_id": tid} for b in data.get("bookings", [])],
        "tenant_id,ext_id",
    )

    # TODO: 갱신된 session_cookie 를 pos_credentials 에 암호화 저장(재로그인 회피)

    return {
        "customers": len(cust_rows),
        "transactions": len(data.get("transactions", [])),
        "bookings": len(data.get("bookings", [])),
    }
