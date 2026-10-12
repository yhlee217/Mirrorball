"""앱에만 있는 데이터 주 1회 백업 · 되살리기(개선 계획 v5 P1).

매출·방문·예약은 HandSOS 에서 다시 수집하면 되지만, 디자이너가 앱에서 쌓은 것은 되살릴 곳이 없다:
메모 · 취향 태그 · 이탈 표시 · 성별 지정(손님) · 사비 결제 표시(거래) · 연락 기록 · 휴무·기준 설정과
디자이너·살롱 이름(매장) · 공개 프로필 · 멤버십 · HandSOS 접속 정보(이미 KEK 로 감싼 값).
손님 이름·전화는 담지 않는다 — 다시 수집하면 돌아온다.

- 매장별 JSON 을 KEK 로 감싸 {MIRRORBALL_BACKUP_DIR}/{날짜}/{slug}.json.enc 로 남긴다(기본 ~/Mirrorball-backups).
  56일(8주) 지난 날짜 폴더는 지운다. KEK 를 바꾸면 worker/rotate_kek.py 가 이 파일들도 다시 감싼다.
- 손님·거래는 고객번호·거래번호(ext_id)로 묶는다 — DB 를 새로 만들어 다시 수집한 뒤에도 이어 붙는다.
- 끝나면 ops_events 에 'backup' 을 남긴다 — sync-health 가 매일 보고 8일 넘게 없으면 알린다.

사용:
    .venv/bin/python worker/backup.py                          # 백업(일요일 수집 직후 run_mac.sh 가 부른다)
    .venv/bin/python worker/backup.py --restore 파일            # 되살리기 미리 보기 — 바꾸지 않는다
    .venv/bin/python worker/backup.py --restore 파일 --apply    # 되살리기
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag

from env import load_env

load_env()

import mirrorball_crypto as mc  # noqa: E402

KEEP_DAYS = 56
VERSION = 1


def backup_dir() -> str:
    return os.environ.get("MIRRORBALL_BACKUP_DIR") or str(Path.home() / "Mirrorball-backups")


# ── 담기·풀기 (네트워크와 분리 — 테스트 가능) ────────────────────────────────

def collect(tenant: dict, customers: list[dict], pocket: list[str], contacts: list[dict],
            profile: dict | None, memberships: list[dict], creds: dict | None, at: str) -> dict:
    """한 매장의 백업 내용. customers 는 id·ext_id 와 앱 칸들, contacts 는 customer_id 로 온다."""
    ext_of = {c["id"]: c.get("ext_id") for c in customers}
    keep = [
        {"ext_id": c["ext_id"], "memo": c.get("memo"), "prefer_tags": c.get("prefer_tags") or [],
         "churned_at": c.get("churned_at"), "gender_manual": c.get("gender_manual")}
        for c in customers
        if c.get("ext_id") and (c.get("memo") or c.get("prefer_tags") or c.get("churned_at") or c.get("gender_manual"))
    ]
    return {
        "v": VERSION,
        "at": at,
        "tenant": {k: tenant.get(k) for k in ("id", "slug", "salon_name", "designer_name", "settings")},
        "customers": keep,
        "pocket": sorted(p for p in pocket if p),
        "contacts": [
            {"ext_id": ext_of.get(c.get("customer_id")), "why": c.get("why"), "sent_at": c.get("sent_at")}
            for c in contacts if ext_of.get(c.get("customer_id"))
        ],
        "profile": profile,
        "memberships": [{"user_id": m.get("user_id"), "role": m.get("role")} for m in memberships],
        "credentials": creds,
    }


def seal(payload: dict, key: bytes) -> str:
    return mc.seal_with(key, json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def unseal(text: str, keys: list[bytes]) -> dict:
    """지금 KEK 로, 안 되면 옛 KEK 로(교체 중) 푼다."""
    for k in keys:
        try:
            return json.loads(mc.open_with(k, text.strip()).decode("utf-8"))
        except InvalidTag:
            continue
    raise InvalidTag("백업 파일이 지금 키·옛 키 어느 쪽으로도 안 풀린다")


def plan_restore(payload: dict, ids: dict[str, str], existing: set[tuple[str, str]]) -> dict:
    """되살릴 일 — ids: 지금 DB 의 고객번호 → 손님 id, existing: 이미 있는 연락 (손님 id, 시각).

    지금 DB 에 없는 손님은 건너뛴다(수집이 아직 안 됐거나 HandSOS 에서 지워진 분).
    """
    custs = [c for c in payload["customers"] if c["ext_id"] in ids]
    contacts = [
        {"customer_id": ids[c["ext_id"]], "why": c["why"], "sent_at": c["sent_at"]}
        for c in payload["contacts"]
        if c["ext_id"] in ids and (ids[c["ext_id"]], c["sent_at"]) not in existing
    ]
    return {
        "customers": [{"id": ids[c["ext_id"]], **{k: c[k] for k in ("memo", "prefer_tags", "churned_at", "gender_manual")}}
                      for c in custs],
        "missing": len(payload["customers"]) - len(custs),
        "pocket": payload["pocket"],
        "contacts": contacts,
    }


def prune(root: Path, today: dt.date, keep_days: int = KEEP_DAYS) -> list[str]:
    """keep_days 지난 날짜 폴더를 지운다. 이름이 날짜가 아닌 폴더는 건드리지 않는다."""
    gone = []
    if not root.exists():
        return gone
    for d in root.iterdir():
        try:
            day = dt.date.fromisoformat(d.name)
        except ValueError:
            continue
        if d.is_dir() and (today - day).days > keep_days:
            shutil.rmtree(d)
            gone.append(d.name)
    return sorted(gone)


def rewrap_files(root: Path, new: bytes, old: bytes, apply: bool) -> tuple[int, int, int]:
    """KEK 교체 때 백업 파일도 새 키로(worker/rotate_kek.py). (다시 감싼 수, 이미 새 키, 안 풀림)."""
    done = already = failed = 0
    for f in sorted(root.glob("*/*.json.enc")) if root.exists() else []:
        text = f.read_text(encoding="utf-8").strip()
        try:
            mc.open_with(new, text)
            already += 1
            continue
        except InvalidTag:
            pass
        try:
            plain = mc.open_with(old, text)
        except InvalidTag:
            failed += 1
            continue
        if apply:
            tmp = f.with_suffix(".tmp")
            tmp.write_text(mc.seal_with(new, plain), encoding="utf-8")
            tmp.replace(f)  # 다 쓴 뒤에 바꾼다 — 중간에 끊겨도 원본이 남는다
        done += 1
    return done, already, failed


# ── 실행 ──────────────────────────────────────────────────────────────────

def _all(path: str, params: dict) -> list:
    """1,000행씩 끝까지(안정 정렬 id)."""
    import supa
    out, off = [], 0
    while True:
        part = supa._get(path, {**params, "order": "id", "limit": "1000", "offset": str(off)})
        out += part
        if len(part) < 1000:
            return out
        off += 1000


def run_backup() -> int:
    import supa

    key = mc._kek()
    now = dt.datetime.now(dt.timezone.utc)
    day = now.astimezone(dt.timezone(dt.timedelta(hours=9))).date()
    root = Path(backup_dir())
    folder = root / day.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    bad = 0
    for t in supa._get("/tenants", {"select": "id,slug,salon_name,designer_name,settings", "order": "slug"}):
        tid, slug = t["id"], t.get("slug") or t["id"][:8]
        try:
            q = {"tenant_id": f"eq.{tid}"}
            customers = _all("/customers", {**q, "select": "id,ext_id,memo,prefer_tags,churned_at,gender_manual"})
            pocket = [r["ext_id"] for r in _all("/transactions", {**q, "paid_out_of_pocket": "is.true", "select": "id,ext_id"})]
            contacts = _all("/care_items", {**q, "kind": "eq.contact", "select": "id,customer_id,why,sent_at"})
            prof = supa._get("/profiles", {**q, "select": "*"})
            mem = supa._get("/memberships", {**q, "select": "user_id,role"})
            cred = supa._get("/pos_credentials", {**q, "select": "provider,enc_blob,session_cookie,status"})
            payload = collect(t, customers, pocket, contacts, prof[0] if prof else None, mem, cred[0] if cred else None,
                              now.isoformat())
            (folder / f"{slug}.json.enc").write_text(seal(payload, key), encoding="utf-8")
            n = {"customers": len(payload["customers"]), "pocket": len(payload["pocket"]),
                 "contacts": len(payload["contacts"])}
            print(f"  [{slug}] 손님 기록 {n['customers']}명 · 사비 표시 {n['pocket']}건 · 연락 {n['contacts']}건")
            try:
                supa.insert("ops_events", [{"tenant_id": tid, "kind": "backup", "detail": n}])
            except Exception as exc:  # noqa: BLE001 — 기록 실패가 백업을 무르게 하지 않게
                print(f"    (백업 시각 기록 실패 — 0023 마이그레이션 적용 확인): {str(exc)[:120]}")
        except Exception as exc:  # noqa: BLE001 — 한 매장 실패가 다른 매장 백업을 막지 않게
            print(f"X [{slug}] 백업 실패: {str(exc)[:200]}")
            bad += 1
    gone = prune(root, day)
    print(f"백업 {folder}" + (f" · 지난 백업 {len(gone)}개 정리" if gone else ""))
    return 1 if bad else 0


def run_restore(path: str, apply: bool) -> int:
    import supa

    keys = [mc._kek()] + ([mc._kek_old()] if mc._kek_old() else [])
    payload = unseal(Path(path).read_text(encoding="utf-8"), keys)
    slug = payload["tenant"]["slug"]
    rows = supa._get("/tenants", {"slug": f"eq.{slug}", "select": "id,settings,designer_name,salon_name"})
    if not rows:
        print(f"X 매장 '{slug}' 이(가) 지금 DB 에 없습니다 — 먼저 매장을 만들고 수집하세요")
        return 1
    tid = rows[0]["id"]
    q = {"tenant_id": f"eq.{tid}"}
    ids = {c["ext_id"]: c["id"] for c in _all("/customers", {**q, "select": "id,ext_id"}) if c.get("ext_id")}
    existing = {(c["customer_id"], c["sent_at"]) for c in _all("/care_items", {**q, "kind": "eq.contact",
                                                                             "select": "id,customer_id,sent_at"})}
    plan = plan_restore(payload, ids, existing)
    print(f"[{slug}] {payload['at'][:10]} 백업 — 손님 기록 {len(plan['customers'])}명"
          f"(지금 DB 에 없는 손님 {plan['missing']}명 건너뜀) · 사비 표시 {len(plan['pocket'])}건 · "
          f"연락 {len(plan['contacts'])}건 · 설정·이름" + (" · 프로필" if payload.get("profile") else ""))
    if not apply:
        print("미리 보기 — 바꾸려면 --apply")
        return 0
    for c in plan["customers"]:
        supa.patch("customers", {"id": f"eq.{c['id']}"}, {k: c[k] for k in ("memo", "prefer_tags", "churned_at", "gender_manual")})
    for i in range(0, len(plan["pocket"]), 200):
        chunk = plan["pocket"][i:i + 200]
        supa.patch("transactions", {**q, "ext_id": "in.(" + ",".join(f'"{x}"' for x in chunk) + ")"},
                   {"paid_out_of_pocket": True})
    supa.insert("care_items", [{"tenant_id": tid, "kind": "contact", **c} for c in plan["contacts"]])
    t = payload["tenant"]
    supa.patch("tenants", {"id": f"eq.{tid}"},
               {k: t[k] for k in ("settings", "designer_name", "salon_name") if t.get(k) is not None})
    if payload.get("profile"):
        supa.upsert("profiles", [{**payload["profile"], "tenant_id": tid}], "tenant_id")
    if payload.get("credentials") and not supa._get("/pos_credentials", {**q, "select": "tenant_id"}):
        supa.upsert("pos_credentials", [{**payload["credentials"], "tenant_id": tid}], "tenant_id")
    print("되살림 끝 — 앱에서 메모·연락 기록이 보이는지 확인하세요")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restore", metavar="파일")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    return run_restore(a.restore, a.apply) if a.restore else run_backup()


if __name__ == "__main__":
    sys.exit(main())
