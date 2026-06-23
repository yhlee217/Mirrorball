"""통계 산출 테스트 — compute()."""

from datetime import date

import stats


RECS = [
    {"date": "2026-04-02", "time": "14:00", "name": "지우", "service": "레이어드펌", "phone": "010-1", "price": 180000},
    {"date": "2026-05-10", "time": "15:00", "name": "지우", "service": "컷", "phone": "010-1", "price": 30000},
    {"date": "2026-05-22", "time": "13:00", "name": "이손님", "service": "컬러", "phone": "010-5", "price": 120000},
    {"date": "2026-06-05", "time": "16:00", "name": "박손님", "service": "발레아주", "phone": "010-3", "price": 90000},
    {"date": "2026-06-23", "time": "14:00", "name": "지우", "service": "레이어드펌", "phone": "010-1", "price": 180000},
    {"date": "2026-06-23", "time": "16:30", "name": "최신규", "service": "컷", "phone": "010-7", "price": 30000},
]
TODAY = date(2026, 6, 23)


def test_counts_and_period():
    s = stats.compute(RECS, TODAY)
    assert s["total_visits"] == 6
    assert s["period"] == {"first": "2026-04-02", "last": "2026-06-23"}
    assert s["this_month"] == 3 and s["last_month"] == 2  # 6월 3건, 5월 2건


def test_revisit_and_new():
    s = stats.compute(RECS, TODAY)
    assert s["unique_customers"] == 4          # 지우·이손님·박손님·최신규
    assert s["returning_customers"] == 1       # 지우만 2회+
    assert s["revisit_rate"] == 25
    assert s["new_this_month"] == 2            # 박손님·최신규 (첫 방문이 6월)


def test_top_services_and_price():
    s = stats.compute(RECS, TODAY)
    assert s["top_services"][0]["name"] == "레이어드펌"
    assert s["top_services"][0]["count"] == 2
    assert s["avg_price"] == round((180000 + 30000 + 120000 + 90000 + 180000 + 30000) / 6)
    assert s["revenue_this_month"] == 90000 + 180000 + 30000  # 6월 3건


def test_phone_dedup_distinguishes_same_name():
    recs = [
        {"date": "2026-06-01", "name": "김", "phone": "010-1", "service": "컷"},
        {"date": "2026-06-02", "name": "김", "phone": "010-2", "service": "컷"},  # 동명이인
    ]
    s = stats.compute(recs, TODAY)
    assert s["unique_customers"] == 2          # 전화로 구분


def test_monthly_series_length():
    s = stats.compute(RECS, TODAY)
    assert len(s["monthly"]) == 6
    assert s["monthly"][-1]["ym"] == "2026-06" and s["monthly"][-1]["count"] == 3


def test_empty():
    s = stats.compute([], TODAY)
    assert s["total_visits"] == 0 and s["revisit_rate"] == 0
