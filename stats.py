#!/usr/bin/env python3
"""누적 예약 장부(records.yaml) → 관리·통계 데이터.

네이버 예약은 실시간 목록을 주지만 '분석'은 안 해준다. import_naver 로 쌓은
장부에서 재방문율·인기 시술·월별 추이·객단가 등을 결정적으로 계산한다.

사용법:
    python stats.py clients/minji            # 통계 요약 출력
    python stats.py clients/minji --json     # JSON 출력(앱 주입용)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import yaml


def _pd(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _months_back(today: date, n: int) -> list[str]:
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


# 정보 미저장 워크인(불특정 다수) — 식별 불가하므로 고객수·재방문율 집계에서 제외(매출·시술엔 포함)
ANON_NAMES = {"손님", "고객", "비회원", "무명", "내방", "워크인"}


def _cust_key(r: dict) -> str:
    """고객 식별: 전화 우선(동명이인 구분), 없으면 이름. 불특정 다수는 빈 키(집계 제외)."""
    name = (r.get("name") or "").strip()
    if name in ANON_NAMES:
        return ""
    ph = "".join(ch for ch in str(r.get("phone") or "") if ch.isdigit())
    return ph or name


WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def compute(records: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    rows = [r for r in records if _pd(r.get("date"))]
    if not rows:
        return {"total_visits": 0, "period": None, "monthly": [], "top_services": [],
                "unique_customers": 0, "returning_customers": 0, "anon_visits": 0,
                "revisit_rate": 0, "this_month": 0, "last_month": 0}

    dates = sorted(_pd(r["date"]) for r in rows)
    this_ym, prev = _ym(today), _months_back(today, 2)[0]

    by_month = Counter(_ym(_pd(r["date"])) for r in rows)
    monthly = [{"ym": ym, "count": by_month.get(ym, 0)} for ym in _months_back(today, 6)]

    services = Counter((r.get("service") or "기타").strip() for r in rows)
    total = sum(services.values())
    top_services = [
        {"name": s, "count": c, "pct": round(c * 100 / total)}
        for s, c in services.most_common(5)
    ]

    # 고객별 방문 횟수
    visits = defaultdict(int)
    first_seen = {}
    for r in rows:
        k = _cust_key(r)
        if not k:
            continue
        visits[k] += 1
        d = _pd(r["date"])
        if k not in first_seen or d < first_seen[k]:
            first_seen[k] = d
    unique = len(visits)
    returning = sum(1 for v in visits.values() if v >= 2)
    anon_visits = sum(1 for r in rows if (r.get("name") or "").strip() in ANON_NAMES)
    new_this_month = sum(1 for k, d in first_seen.items() if _ym(d) == this_ym)

    weekday = Counter(WEEKDAYS[_pd(r["date"]).weekday()] for r in rows)
    hours = Counter(str(r.get("time") or "")[:2] for r in rows if r.get("time"))

    prices = [r["price"] for r in rows if isinstance(r.get("price"), (int, float))]
    revenue_month = sum(
        r["price"] for r in rows
        if isinstance(r.get("price"), (int, float)) and _ym(_pd(r["date"])) == this_ym
    )

    return {
        "total_visits": len(rows),
        "period": {"first": str(dates[0]), "last": str(dates[-1])},
        "this_month": by_month.get(this_ym, 0),
        "last_month": by_month.get(prev, 0),
        "monthly": monthly,
        "unique_customers": unique,
        "returning_customers": returning,
        "anon_visits": anon_visits,        # 정보 미저장 워크인 방문 수(고객수·재방문율 분모에서 제외)
        "new_this_month": new_this_month,
        "revisit_rate": round(returning * 100 / unique) if unique else 0,
        "top_services": top_services,
        "busiest_weekday": (weekday.most_common(1)[0][0] + "요일") if weekday else None,
        "busiest_hour": (hours.most_common(1)[0][0] + "시") if hours else None,
        "avg_price": round(sum(prices) / len(prices)) if prices else None,
        "revenue_this_month": revenue_month or None,
    }


def load_records(client_dir: str) -> list[dict]:
    p = Path(client_dir) / "records.yaml"
    if not p.exists():
        return []
    return yaml.safe_load(p.read_text(encoding="utf-8")) or []


def main() -> int:
    ap = argparse.ArgumentParser(description="예약 장부 → 통계")
    ap.add_argument("client_dir", help="clients/{slug}")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    s = compute(load_records(args.client_dir))
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0

    if not s["total_visits"]:
        print("기록이 없습니다. import_naver.py 로 예약을 적재하세요.")
        return 0
    print(f"기간: {s['period']['first']} ~ {s['period']['last']}  ·  총 {s['total_visits']}건")
    print(f"이번 달 {s['this_month']}건 (지난달 {s['last_month']}건)")
    print(f"고객 {s['unique_customers']}명 · 재방문 {s['returning_customers']}명 "
          f"· 재방문율 {s['revisit_rate']}% · 이번 달 신규 {s['new_this_month']}명")
    if s.get("anon_visits"):
        print(f"(정보 미저장 워크인 {s['anon_visits']}건은 고객수·재방문율에서 제외)")
    if s["busiest_weekday"]:
        print(f"가장 바쁜 요일/시간: {s['busiest_weekday']} {s['busiest_hour'] or ''}")
    if s["avg_price"]:
        print(f"객단가 평균 {s['avg_price']:,}원 · 이번 달 매출 {s['revenue_this_month'] or 0:,}원")
    print("인기 시술:")
    for t in s["top_services"]:
        print(f"  - {t['name']}: {t['count']}건 ({t['pct']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
