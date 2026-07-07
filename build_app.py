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
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

import copydata
import crosssell as _crosssell
import drafts
import relations


def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


# 전화번호 PII 안전망 — 메모/노트 등 자유입력에 섞인 번호를 앱 데이터에서 일괄 마스킹.
# 국내(010-…)와 국제표기(+82 10-…, 선행 0 생략) 모두 포착. 접두(0 또는 +82)는 필수라 임의 숫자열 오탐 방지.
_PHONE_RE = re.compile(r"(?:\+?82[-.\s]?0?|0)1[016789][-.\s]?\d{3,4}[-.\s]?\d{4}")


def _redact_pii(obj):
    if isinstance(obj, str):
        return _PHONE_RE.sub("[연락처]", obj)
    if isinstance(obj, list):
        return [_redact_pii(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact_pii(v) for k, v in obj.items()}
    return obj


def _parse_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    return datetime.strptime(str(v), "%Y-%m-%d").date()


def _md(v) -> tuple[int, int] | None:
    """'MM-DD' → (month, day). 대시 없는/형식 불량 입력은 조용히 건너뜀(JS 가드와 일치)."""
    if not v:
        return None
    parts = str(v).split("-")
    if len(parts) < 2:
        return None
    try:
        return int(parts[-2]), int(parts[-1])
    except ValueError:
        return None


def last_visit(cust: dict) -> date | None:
    dates = [_parse_date(h.get("date")) for h in cust.get("history", []) or []]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def _visit_dates(cust: dict) -> list[date]:
    ds = {_parse_date(h.get("date")) for h in cust.get("history", []) or []}
    return sorted(d for d in ds if d)


def derive_cycle(cust: dict) -> int:
    """개인별 재방문 주기(일). 명시값 우선, 없으면 방문 간격 중앙값(10~120 클램프)."""
    cyc = cust.get("care_cycle_days")
    if cyc:
        return int(cyc)
    ds = _visit_dates(cust)
    if len(ds) < 2:
        return 0
    iv = sorted((ds[i + 1] - ds[i]).days for i in range(len(ds) - 1))
    n = len(iv)
    # round-half-up (정수 간격) — JS Math.round 와 일치(파이썬 기본 banker's rounding 회피)
    med = iv[n // 2] if n % 2 else (iv[n // 2 - 1] + iv[n // 2] + 1) // 2
    return max(10, min(120, med))


def revisit_state(cust: dict, today: date) -> dict:
    """재방문 상태: overdue(이탈위험)·due(도래)·soon·new·ok + 주기/경과일.

    배포 JSON 은 기본(보통) 민감도 스냅샷. 앱은 시드에서 사용자 선택 프리셋(느슨/보통/민감)으로
    런타임 재산출하므로 new 임계(여기선 60일 고정)는 앱에서 45/60/90 으로 달라질 수 있다(의도).
    """
    lv = last_visit(cust)
    v = cust.get("loyalty_visits") or len(cust.get("history", []) or [])
    cyc = derive_cycle(cust)
    explicit = bool(cust.get("care_cycle_days"))   # 직접 지정한 주기는 방문 1회여도 신뢰
    gap = (today - lv).days if lv else None
    if gap is None or not cyc or (v < 2 and not explicit):
        state = "new" if (v <= 1 and gap is not None and 0 <= gap <= 60) else "ok"
    elif gap >= 400:
        state = "ok"                       # 휴면(장기 미방문) — 주기 신호 대상 아님
    elif (v >= 3 or explicit) and gap > cyc * 1.6:
        state = "overdue"
    elif gap >= cyc * 0.9:
        state = "due"
    elif gap >= cyc * 0.7:
        state = "soon"
    else:
        state = "ok"
    return {"cycle": cyc, "gap": gap, "state": state}


def alerts_for(cust: dict, today: date, window: int = 7) -> list[dict]:
    """한 고객에 대한 오늘의 알림(0~N개). 재방문 주기는 이력에서 자동 추정."""
    out: list[dict] = []
    bd = _md(cust.get("birthday"))
    if bd and (today.month, today.day) == bd:
        out.append({"kind": "bday", "label": "생일", "why": "오늘 생일"})

    ri = revisit_state(cust, today)
    svc = _latest_service(cust) or "시술"
    if ri["state"] == "overdue":
        out.append({"kind": "atrisk", "label": "이탈 위험",
                    "why": f"{svc} · {ri['gap']}일째 안 오심(평소 {ri['cycle']}일 주기)"})
    elif ri["state"] == "due":
        out.append({"kind": "revisit", "label": "재방문",
                    "why": f"{svc} 리터치 시기 · {ri['gap']}일째(평소 {ri['cycle']}일)"})
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


def _custno_key(v) -> str:
    """고객번호 정규화(숫자만 + 앞 0 제거). 원장·고객 양쪽이 같은 키를 쓰게 하는 단일 소스."""
    return re.sub(r"\D", "", str(v or "")).lstrip("0")


def spend_by_custno(records: list[dict]) -> dict[str, int]:
    """거래 원장 → 고객번호별 누적결제(원). LTV·VIP 산정의 단일 소스."""
    spend: dict[str, int] = {}
    for r in records or []:
        cn = _custno_key(r.get("custno"))
        p = r.get("price")
        if cn and isinstance(p, (int, float)):
            spend[cn] = spend.get(cn, 0) + int(p)
    return spend


# 누적결제 기준 등급 경계 — **단일 소스**. dist JSON 의 thresholds 로 내보내 앱 JS 도 이 값을 쓴다.
TIER_THRESHOLDS = {"vip": 500000, "regular": 250000, "normal": 100000}


def spend_tier(won: int) -> str:
    if won >= TIER_THRESHOLDS["vip"]:
        return "vip"
    if won >= TIER_THRESHOLDS["regular"]:
        return "regular"
    if won >= TIER_THRESHOLDS["normal"]:
        return "normal"
    return "light"


def build_customer(cust: dict, today: date | None = None) -> dict:
    """앱 화면용 고객 카드(연락처 등 PII 는 출력에서 제외)."""
    import aftercare

    lv = last_visit(cust)
    svc = _latest_service(cust)
    ri = revisit_state(cust, today or date.today())
    won = int(cust.get("total_won") or 0)
    return {
        "id": cust.get("id"),
        "custno": cust.get("custno", ""),     # 핸드SOS 고객번호(PK)
        "name": cust.get("name"),
        "memo": cust.get("memo", ""),
        "prefer": cust.get("prefer", []),
        "loyalty_visits": cust.get("loyalty_visits", len(cust.get("history", []) or [])),
        "first_visit": str(cust["first_visit"]) if cust.get("first_visit") else None,
        "last_visit": str(lv) if lv else None,
        "care_cycle_days": ri["cycle"],   # 방문 간격에서 자동 추정(없으면 명시값)
        "days_since": ri["gap"],
        "revisit_state": ri["state"],     # overdue·due·soon·new·ok
        "total_won": won,                 # 누적결제(records 합산) — LTV
        "tier": spend_tier(won),          # vip·regular·normal·light
        # 교차판매 — 파이썬(crosssell.py, 테스트됨)이 단일 소스. 앱 JS 는 이 값을 렌더만.
        "crosssell": _crosssell.crosssell_for(cust),
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
    cfg_path = Path(client_dir) / "config.yaml"
    cfg = _load(str(cfg_path)) if cfg_path.exists() else {}   # 없으면 기본값으로 진행
    slug = cfg.get("slug") or Path(client_dir).name
    today = _parse_date(cfg.get("today")) or date.today()

    cust_paths = sorted(glob.glob(str(Path(client_dir) / "customers" / "*.yaml")))
    customers = [_load(p) for p in cust_paths]

    # 누적결제(LTV) 주입 — 거래 원장에서 고객번호별 합산해 카드·시드 양쪽에 실어준다.
    import stats as _stats
    records = _stats.load_records(client_dir)
    spend = spend_by_custno(records)
    for c in customers:
        c["total_won"] = spend.get(_custno_key(c.get("custno")), 0)   # 조회 키도 동일 정규화

    care_list = []
    for c in customers:
        for a in alerts_for(c, today):
            care_list.append({
                "id": c.get("id"), "name": c.get("name"),
                "kind": a["kind"], "label": a["label"], "why": a["why"],
                "prefer": c.get("prefer", []),
                "draft": drafts.draft_for(a["kind"], c, today,    # 추천 문구(초안)
                                          salon=cfg.get("salon", ""),
                                          designer=cfg.get("display_name", slug)),
            })
    # 생일 → 이탈위험 → 재방문 도래 순
    order = {"bday": 0, "atrisk": 1, "revisit": 2}
    care_list.sort(key=lambda x: order.get(x["kind"], 9))

    bookings = resolve_bookings(client_dir, customers, today)

    clients = [build_customer(c, today) for c in customers]
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
    if records:
        data["stats"] = _stats.compute(records, today)

    # AI 노출 진단 결과(diagnose.py 산출)가 있으면 노출 탭에 주입.
    exp_path = Path(client_dir) / "exposure.yaml"
    if exp_path.exists():
        data["exposure"] = _load(str(exp_path))

    # 인스타 발견 지표(insta.py 산출)가 있으면 노출 탭 '인스타' 섹션에 주입.
    ig_path = Path(client_dir) / "instagram.yaml"
    if ig_path.exists():
        data["instagram"] = _load(str(ig_path))

    # 규칙 상수 단일화 — 앱 JS 가 이 값을 읽어 파이썬과 드리프트 없게(⑤)
    data["thresholds"] = {"tiers": TIER_THRESHOLDS}

    out = Path(dist) / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = _redact_pii(data)   # 메모 등 자유입력에 섞인 전화번호 최종 마스킹(PII 안전망)
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
