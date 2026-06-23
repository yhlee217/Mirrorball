#!/usr/bin/env python3
"""원장용 컨시어지 앱 데이터 빌더 (Phase 2).

고객 YAML(비공개) → 앱이 읽는 JSON 한 장.
컨시어지가 로컬에서 실행, 결과 JSON 만 게이트된 배포물에 올린다.

사용법:
    python build_app.py clients/minji          # 한 디자이너
    python build_app.py --all                  # clients/*/ 전부
    출력: dist_app/{slug}.json

핵심 로직 = "오늘 챙길 고객" 산출.  *자동 발송하지 않는다* — 원장에게 알림만.
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


def build_customer(cust: dict) -> dict:
    """앱 화면용 고객 카드(연락처 등 PII 는 출력에서 제외)."""
    lv = last_visit(cust)
    return {
        "id": cust.get("id"),
        "name": cust.get("name"),
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
        # contact 는 의도적으로 제외 — 원장 로컬에만 존재, 배포물 미포함
    }


def _digits(s) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def resolve_bookings(client_dir: str, customers: list[dict], today: date) -> list[dict]:
    """오늘의 예약 목록(name·service·time·id). 연락처(PII)는 출력하지 않는다.

    우선순위: clients/{slug}/bookings.yaml(네이버 예약 내보내기) → 없으면 고객 yaml 의 booking.
    네이버 예약 행은 이름/전화로 기존 고객과 매칭해 id 를 연결(없으면 id=null).
    """
    by_phone = {_digits(c.get("contact")): c for c in customers if _digits(c.get("contact"))}
    by_name = {(c.get("name") or "").strip(): c for c in customers if c.get("name")}

    bpath = Path(client_dir) / "bookings.yaml"
    nv = _load(str(bpath)) if bpath.exists() else None
    rows: list[dict]
    if isinstance(nv, list) and nv:
        rows = []
        for b in nv:
            if str(b.get("date")) != str(today):     # 오늘 예약만
                continue
            cust = by_phone.get(_digits(b.get("phone"))) or by_name.get((b.get("name") or "").strip())
            rows.append({
                "name": b.get("name"),
                "service": b.get("service"),
                "time": b.get("time"),
                "id": cust.get("id") if cust else None,   # 매칭 실패해도 표시
            })
    else:
        rows = [
            {"name": c.get("name"),
             "service": (c.get("booking") or {}).get("service"),
             "time": (c.get("booking") or {}).get("time"),
             "id": c.get("id")}
            for c in customers
            if c.get("booking") and str(_parse_date((c["booking"]).get("date"))) == str(today)
        ]
    rows.sort(key=lambda r: (r.get("time") or ""))
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
                "draft": "",  # copygen.py 로 채울 추천 문구(초안)
            })
    # 생일 먼저, 그다음 재방문
    order = {"bday": 0, "revisit": 1}
    care_list.sort(key=lambda x: order.get(x["kind"], 9))

    bookings = resolve_bookings(client_dir, customers, today)

    data = {
        "slug": slug,
        "designer": cfg.get("display_name", slug),
        "salon": cfg.get("salon", ""),
        "today": str(today),
        "bookings": bookings,
        "care": care_list,
        "clients": [build_customer(c) for c in customers],
    }

    out = Path(dist) / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
