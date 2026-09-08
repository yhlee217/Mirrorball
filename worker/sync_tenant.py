"""살롱 1회 수집 → 담당(디자이너)별로 각 테넌트에 분리 업서트(멀티테넌트)."""

from __future__ import annotations

import re
import traceback
from collections import defaultdict
from datetime import date, timedelta

import mirrorball_crypto as mc
import scrape
import supa
import txkind
from scrape import _derive

_PII_FIELDS = ("name", "birthday", "phone")


_SCHEMA_0019: bool | None = None


def _has_0019() -> bool:
    """0019(kind·covered_won·prepaid_balance)가 적용됐는지 한 번만 확인.

    맥의 주간 수집은 사람이 안 보는 채로 돈다. 마이그레이션이 아직 안 걸렸다고 수집 전체가
    죽으면 일주일치를 잃는다. 없으면 없는 대로(시술명으로 판정) 돌고, 있으면 정확히 쓴다.
    """
    global _SCHEMA_0019
    if _SCHEMA_0019 is None:
        try:
            supa._get("/transactions", {"select": "id,kind,covered_won", "limit": "1"})
            supa._get("/customers", {"select": "id,prepaid_balance", "limit": "1"})
            _SCHEMA_0019 = True
        except RuntimeError as exc:
            if "42703" in str(exc) or "does not exist" in str(exc):
                _SCHEMA_0019 = False
                print("  ⚠ 0019 미적용 — 충전 분리 없이 수집만 진행"
                      "(supabase/migrations/0019_transaction_kind.sql 적용 후 recompute.py 권장)")
            else:
                raise
    return _SCHEMA_0019


def _recompute_aggregates(tid: str) -> int:
    """전체 거래로 고객 집계 재계산 — 수집 창과 무관하게 방문수·주기·매출 lifetime 정확.

    방문수는 '시술을 받은 날'만 센다. 충전만 하고 간 날을 방문으로 세면 재방문 주기가 짧아져
    이탈 판정이 밀린다. 같은 날 시술 2건은 날짜 집합이라 원래부터 1회로 센다.

    매출은 선불 원장(txkind.ledger)으로 낸다 — 충전과 그 충전금으로 한 시술을 둘 다 더하면
    이중 계상이라, 실제로 받은 돈만 남긴다.
    """
    full = _has_0019()
    cols = ("id,customer_id,date,time,service,amount_won,kind,paid_out_of_pocket,covered_won"
            if full else "id,customer_id,date,time,service,amount_won")
    txs = supa.select_all("transactions", tid, cols)
    byc: dict = defaultdict(list)
    for t in txs:
        if t.get("customer_id") and t.get("date"):
            byc[t["customer_id"]].append({
                "id": t.get("id"),
                "date": t["date"],
                "time": t.get("time"),
                "amount": t.get("amount_won") or 0,
                # kind 가 아직 없는 행(마이그레이션 전 수집분)은 시술명으로 즉시 판정
                "kind": t.get("kind") or txkind.classify(t.get("service")),
                "out_of_pocket": bool(t.get("paid_out_of_pocket")),
                "covered": t.get("covered_won") or 0,
            })
    today_d = date.today()
    today = str(today_d)
    # VIP 판정용 최근 방문 횟수. 앱이 매번 전체 거래를 훑지 않도록 여기서 미리 센다.
    # 창은 3개 고정 — 설정(vip_recent_months)이 그중 하나를 고르므로 설정을 바꿔도 재수집 불필요.
    cut90, cut180, cut365 = (str(today_d - timedelta(days=n)) for n in (90, 180, 365))
    updates = []
    covered_fix: list = []
    for cid, items in byc.items():
        # 방문 = 시술을 받은 날(충전·제품만 있는 날 제외)
        dates = sorted({it["date"] for it in items if it["kind"] == "service"}, reverse=True)
        cycle, state = _derive(dates, len(dates), today)
        book = txkind.ledger(items)
        # 거래별 '잔액으로 결제된 금액'. 통계는 월별로 합산해야 해서 고객 단위 집계로는 안 되고,
        # 이 값이 있어야 어느 화면이든 '실매출 = 금액 − 잔액결제분' 한 규칙으로 계산된다.
        for it in items:
            want = book["per_tx"].get(it["id"], 0)
            if want != (it.get("covered") or 0):
                covered_fix.append((it["id"], want))
        updates.append({
            "id": cid, "tenant_id": tid, "visit_count": len(dates),
            "first_visit": dates[-1] if dates else None,
            "last_visit": dates[0] if dates else None,
            "total_won": book["revenue"],
            **({"prepaid_balance": book["balance"]} if full else {}),
            "revisit_cycle_days": cycle, "revisit_state": state,
            "visits_90d": sum(1 for d in dates if d >= cut90),
            "visits_180d": sum(1 for d in dates if d >= cut180),
            "visits_365d": sum(1 for d in dates if d >= cut365),
        })
    # 바뀐 거래만 갱신 — 선불 고객은 일부라 보통 몇 건이다.
    for txid, val in (covered_fix if full else []):
        supa.patch("transactions", {"id": f"eq.{txid}"}, {"covered_won": val})
    if full and covered_fix:
        print(f"  잔액결제 반영 {len(covered_fix)}건")
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
            **({"kind": txkind.classify(t.get("service"))} if _has_0019() else {}),
            "ext_id": t["ext_id"],
            # paid_out_of_pocket 은 일부러 넣지 않는다 — 사장님이 표시한 값을 수집이 덮으면 안 된다
            # (업서트가 merge-duplicates 라 payload 에 없는 컬럼은 그대로 남는다).
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
            supa.record_sync(target["id"], out[slug])   # 앱의 '수집 기준일' 근거
            print(f"  OK {slug}: {out[slug]}")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            out[slug] = {"error": str(exc)}
            supa.record_sync(target["id"], None, error=str(exc))
    return out
