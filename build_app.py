#!/usr/bin/env python3
"""디자이너용 컨시어지 앱 데이터 빌더 (Phase 2).

고객 YAML(비공개) → 앱이 읽는 JSON 한 장.
컨시어지가 로컬에서 실행, 결과 JSON 만 게이트된 배포물에 올린다.

사용법:
    python build_app.py clients/minji          # 한 디자이너
    python build_app.py --all                  # clients/*/ 전부
    출력: dist_app/{slug}.json

핵심 로직 = "오늘 챙길 고객" 산출.  *자동 발송하지 않는다* — 디자이너에게 알림만.
  · 생일: birthday 가 오늘
  · 재방문: 마지막 시술 + care_cycle_days 가 지났거나 7일 내 도래
산출은 결정적(LLM 불필요). 추천 문구 초안만 비워두면 copygen.py 로 채울 수 있다.
"""

from __future__ import annotations

import glob
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

import copydata
import drafts
import relations


def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _parse_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    return datetime.strptime(str(v), "%Y-%m-%d").date()


def _md(v) -> tuple[int, int] | None:
    """'MM-DD' → (month, day)."""
    if not v:
        return None
    m, d = str(v).split("-")[-2:]
    return int(m), int(d)


def last_visit(cust: dict) -> date | None:
    dates = [_parse_date(h.get("date")) for h in cust.get("history", []) or []]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def alerts_for(cust: dict, today: date, window: int = 7) -> list[dict]:
    """한 고객에 대한 오늘의 알림(0~N개)."""
    out: list[dict] = []
    bd = _md(cust.get("birthday"))
    if bd and (today.month, today.day) == bd:
        out.append({"kind": "bday", "label": "생일", "why": "오늘 생일"})

    lv = last_visit(cust)
    cyc = cust.get("care_cycle_days")
    if lv and cyc:
        due = lv + timedelta(days=int(cyc))
        days_left = (due - today).days
        if days_left <= window:
            svc = (cust.get("history") or [{}])[-1].get("service", "시술")
            overdue = "지남" if days_left < 0 else f"{days_left}일 내"
            out.append({
                "kind": "revisit", "label": "재방문",
                "why": f"{svc} 리터치 시기({overdue})",
            })
    return out


def _clean_booking(b: dict | None) -> dict | None:
    if not b:
        return None
    out = dict(b)
    if out.get("date") is not None:
        out["date"] = str(_parse_date(out.get("date")))
    return out


def _latest_service(cust: dict) -> str | None:
    best_d, best_s = None, None
    for h in cust.get("history", []) or []:
        d = _parse_date(h.get("date"))
        if d and (best_d is None or d > best_d):
            best_d, best_s = d, h.get("service")
    return best_s


def build_customer(cust: dict) -> dict:
    """앱 화면용 고객 카드(연락처 등 PII 는 출력에서 제외)."""
    import aftercare

    lv = last_visit(cust)
    svc = _latest_service(cust)
    return {
        "id": cust.get("id"),
        "name": cust.get("name"),
        "memo": cust.get("memo", ""),
        "prefer": cust.get("prefer", []),
        "loyalty_visits": cust.get("loyalty_visits", len(cust.get("history", []) or [])),
        "first_visit": str(cust["first_visit"]) if cust.get("first_visit") else None,
        "last_visit": str(lv) if lv else None,
        "booking": _clean_booking(cust.get("booking")),
        "history": [
            {"date": str(_parse_date(h.get("date"))), "service": h.get("service"),
             "notes": h.get("notes")}
            for h in (cust.get("history") or [])
        ],
        # 마지막 시술 기준 애프터케어 팁(방문 후 디자이너가 직접 전송)
        "aftercare": aftercare.tips_for(svc) if svc else [],
        # contact 는 의도적으로 제외 — 디자이너 로컬에만 존재, 배포물 미포함
    }


def _digits(s) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def resolve_bookings(client_dir: str, customers: list[dict], today: date) -> list[dict]:
    """다가오는 예약 목록(오늘 이후, name·service·time·id·date). 연락처(PII)는 제외.

    우선순위: clients/{slug}/bookings.yaml(네이버 예약 내보내기) → 없으면 고객 yaml 의 booking.
    네이버 예약 행은 이름/전화로 기존 고객과 매칭해 id 를 연결(없으면 id=null).
    """
    by_phone = {_digits(c.get("contact")): c for c in customers if _digits(c.get("contact"))}
    by_name = {(c.get("name") or "").strip(): c for c in customers if c.get("name")}
    tstr = str(today)

    bpath = Path(client_dir) / "bookings.yaml"
    nv = _load(str(bpath)) if bpath.exists() else None
    rows: list[dict]
    if isinstance(nv, list) and nv:
        rows = []
        for b in nv:
            d = str(_parse_date(b.get("date")) or b.get("date"))
            if d < tstr:                              # 지난 예약 제외(오늘 이후)
                continue
            cust = by_phone.get(_digits(b.get("phone"))) or by_name.get((b.get("name") or "").strip())
            rows.append({
                "name": b.get("name"), "service": b.get("service"),
                "time": b.get("time"), "date": d,
                "id": cust.get("id") if cust else None,   # 매칭 실패해도 표시
            })
    else:
        rows = []
        for c in customers:
            bk = c.get("booking") or {}
            if not bk:
                continue
            d = str(_parse_date(bk.get("date")) or "")
            if d < tstr:
                continue
            rows.append({"name": c.get("name"), "service": bk.get("service"),
                         "time": bk.get("time"), "date": d, "id": c.get("id")})
    rows.sort(key=lambda r: (r.get("date") or "", r.get("time") or ""))
    return rows


def build_one(client_dir: str, dist: str = "dist_app") -> dict:
    cfg = _load(str(Path(client_dir) / "config.yaml"))
    slug = cfg.get("slug") or Path(client_dir).name
    today = _parse_date(cfg.get("today")) or date.today()

    cust_paths = sorted(glob.glob(str(Path(client_dir) / "customers" / "*.yaml")))
    customers = [_load(p) for p in cust_paths]

    care_list = []
    for c in customers:
        for a in alerts_for(c, today):
            care_list.append({
                "id": c.get("id"), "name": c.get("name"),
                "kind": a["kind"], "label": a["label"], "why": a["why"],
                "prefer": c.get("prefer", []),
                "draft": drafts.draft_for(a["kind"], c, today),  # 추천 문구(초안)
            })
    # 생일 먼저, 그다음 재방문
    order = {"bday": 0, "revisit": 1}
    care_list.sort(key=lambda x: order.get(x["kind"], 9))

    bookings = resolve_bookings(client_dir, customers, today)

    clients = [build_customer(c) for c in customers]
    rel = relations.resolve(customers)            # 가족·친구·소개 관계 해석
    for cd in clients:
        info = rel.get(cd["id"]) or {}
        cd["relations"] = info.get("relations", [])
        cd["referred_by"] = info.get("referred_by")
        cd["referred"] = info.get("referred", [])

    # 앱이 로컬에서 직접 추가·수정할 수 있도록 '원본 입력'도 시드로 제공(연락처 PII 제외).
    seed = [{k: v for k, v in (c or {}).items() if k != "contact"} for c in customers]

    data = {
        "slug": slug,
        "designer": cfg.get("display_name", slug),
        "salon": cfg.get("salon", ""),
        "today": str(today),
        "bookings": bookings,
        "care": care_list,
        "clients": clients,
        "seed": seed,            # 원본 고객 입력(앱 로컬 편집의 출발점)
        # 업종별 카피 데이터 — 앱 JS 가 이 단일 소스로 benefit/aftercare 산출(이중정의 제거)
        "config": {
            "benefit": copydata.benefit(),
            "aftercare": copydata.aftercare(),
            "service_noun": copydata.service_noun(),
            "quick_tags": copydata.quick_tags(),
        },
    }

    # 누적 장부가 있으면 통계 포함 (관리·분석용). PII(전화)는 stats 가 집계만 함.
    recs_path = Path(client_dir) / "records.yaml"
    if recs_path.exists():
        import stats
        data["stats"] = stats.compute(stats.load_records(client_dir), today)

    # AI 노출 진단 결과(diagnose.py 산출)가 있으면 노출 탭에 주입.
    exp_path = Path(client_dir) / "exposure.yaml"
    if exp_path.exists():
        data["exposure"] = _load(str(exp_path))

    out = Path(dist) / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"slug": slug, "out": str(out), "care": len(care_list),
            "clients": len(customers)}


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("사용법: python build_app.py clients/{slug} | --all")
        return 2
    if args[0] == "--all":
        dirs = sorted(d for d in glob.glob("clients/*") if Path(d).is_dir())
        if not dirs:
            print("clients/*/ 가 없습니다")
            return 1
    else:
        dirs = [args[0]]

    rc = 0
    for d in dirs:
        try:
            r = build_one(d)
            print(f"✓ {r['slug']:<12} → {r['out']}  (고객 {r['clients']} · 챙길 {r['care']})")
        except Exception as exc:
            print(f"✗ {d}\n    {exc}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
