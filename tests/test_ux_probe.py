"""UX 사전 측정(worker/ux_probe.py) — 화면과 같은 기준으로 세는지.

측정 기준이 화면과 다르면 '챙길 고객 46명 중 5명'이 실제 화면 숫자와 어긋나 판단을 그르친다.
네트워크·복호화 없이 순수 계산만 본다.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import ux_probe as up  # noqa: E402

NOW = dt.datetime(2026, 10, 12, 15, 0, tzinfo=up.KST)
TODAY = NOW.date()
S = up.lapse_settings(None)


def d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


@pytest.mark.parametrize("b, want", [
    ({"date": d(3), "time": "11:00", "status": "예약"}, True),
    ({"date": d(0), "time": "16:00", "status": None}, True),     # 오늘, 아직 안 지남
    ({"date": d(0), "time": "14:00", "status": None}, False),    # 오늘, 이미 지남
    ({"date": d(0), "time": None, "status": None}, True),        # 시각 모름 → 오늘은 유효
    ({"date": d(-1), "time": "18:00", "status": None}, False),   # 어제
    ({"date": d(3), "time": "11:00", "status": "예약취소"}, False),
    ({"date": d(3), "time": "11:00", "status": "노쇼"}, False),
    ({"date": None, "time": None, "status": None}, False),
])
def test_active_booking_matches_web(b, want):
    assert up.is_active_booking(b, NOW) is want


def test_lapsed_matches_web_defaults():
    assert up.is_lapsed({"last_visit": d(-400), "visit_count": 9}, S, TODAY)      # 12개월 초과
    assert up.is_lapsed({"last_visit": d(-200), "visit_count": 2}, S, TODAY)      # 6개월 초과 & 3회 미만
    assert not up.is_lapsed({"last_visit": d(-200), "visit_count": 5}, S, TODAY)  # 6개월 초과지만 단골
    assert up.is_lapsed({"last_visit": None, "visit_count": 0}, S, TODAY)
    assert up.lapse_settings({"lapsed_months": 24})["lapsed_months"] == 24


def test_last_n_months_wraps_year():
    assert up.last_n_months(dt.date(2026, 2, 10), 6) == [
        "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]


CUSTOMERS = [
    # 챙길 고객 + 다음 주 예약 있음 + 전화 있음
    {"id": "c1", "ext_id": "101", "revisit_state": "overdue", "last_visit": d(-60), "visit_count": 4,
     "first_visit": d(-700), "revisit_cycle_days": 30, "prepaid_balance": 100000, "memo_ai": "- 뿌리펌"},
    # 챙길 고객, 예약 없음, 전화 없음
    {"id": "c2", "ext_id": "102", "revisit_state": "due", "last_visit": d(-40), "visit_count": 3,
     "first_visit": d(-500), "revisit_cycle_days": 35},
    {"id": "c3", "ext_id": "103", "revisit_state": "overdue", "last_visit": d(-90), "visit_count": 6,
     "churned_at": "2026-09-01T00:00:00Z"},                                   # 이탈 표시 → 제외
    {"id": "c4", "ext_id": "104", "revisit_state": "overdue", "last_visit": d(-400), "visit_count": 9},  # 이탈 판정
    {"id": "c5", "ext_id": "W1", "revisit_state": "overdue", "last_visit": d(-50), "visit_count": 2},    # 워크인
    {"id": "c6", "ext_id": "106", "revisit_state": "new", "last_visit": d(-90), "visit_count": 1,
     "first_visit": d(-90)},                                                   # 신규, 아직 1회
    {"id": "c7", "ext_id": "107", "revisit_state": None, "last_visit": d(-20), "visit_count": 2,
     "first_visit": d(-100), "revisit_cycle_days": 80},                        # 신규 → 2회차 전환
]
BOOKINGS = [
    {"customer_id": "c1", "date": d(5), "time": "12:00", "status": "예약"},
    {"customer_id": "c2", "date": d(-10), "time": "12:00", "status": "예약"},   # 지난 예약
    {"customer_id": "c7", "date": d(7), "time": "10:00", "status": "예약취소"},
    {"customer_id": "c6", "date": d(-30), "time": "15:00", "status": "노쇼"},
]
TXS = [
    {"date": d(-10), "time": "14:30"}, {"date": d(-40), "time": "11:00"},
    {"date": d(-200), "time": "19:10"}, {"date": d(-100), "time": ""},
    {"date": d(-500), "time": None},                                          # 12개월 밖 → 제외
]
PHONES = {"c1": True, "c2": False, "c6": True, "c7": True}


def test_measure_counts_like_the_screen():
    m = up.measure(CUSTOMERS, TXS, BOOKINGS, PHONES, S, NOW)
    assert m["customers"] == 6                       # 워크인 제외
    assert m["care"] == 1                            # c2 — c1 은 이미 예약해서 빠진다(P0 1번)
    assert m["care_booked"] == 1                     # c1 만 활성 예약 — 지난·취소 예약은 안 셈
    assert m["care_phone"] == (0, 1)                 # 연락할 사람(c2) 기준
    assert m["phone"] == (3, 6)
    assert m["tx_time"] == (3, 4)                    # 빈 시각 1건, 12개월 밖 1건 제외
    assert m["repeat"] == (5, 6)
    assert m["prepaid"] == (1, 100000)
    assert m["bk_status"] == {"그 외": 2, "취소": 1, "노쇼": 1}
    assert m["bk_past"] == 2
    assert m["convert"] == (1, 2)                    # c6(1회)·c7(2회) 중 c7
    assert m["memo_ai_booked"] == (1, 1)


def test_verdicts_flag_booked_customers():
    m = up.measure(CUSTOMERS, TXS, BOOKINGS, PHONES, S, NOW)
    v = "\n".join(up.verdicts([m]))
    assert "챙길 고객 1명 — 이미 예약해서 빠진 1명 · 최근 연락해서 빠진 0명" in v
    assert "노쇼 기록 1건" in v


def test_report_only_prints_counts():
    """report 는 지표만 받는다 — 이름·전화번호가 들어갈 길이 없다."""
    m = up.measure(CUSTOMERS, TXS, BOOKINGS, PHONES, S, NOW)
    lines = up.report("daunbu", "살롱톤", m)
    assert lines[0] == "[daunbu] 살롱톤"
    assert any("1-1 챙길 고객 1명 — 이미 예약해서 빠진 1명 · 최근 연락해서 빠진 0명" in ln for ln in lines)


def test_recently_contacted_leave_the_todo_list_only():
    """연락한 분은 할 일(탭)에서만 빠지고, 상태(타일)로는 그대로 센다."""
    m = up.measure(CUSTOMERS, TXS, BOOKINGS, PHONES, S, NOW, contacted={"c2"})
    assert m["care"] == 0 and m["care_quiet"] == 1 and m["care_booked"] == 1


def test_first_visit_customers_join_the_care_list():
    """첫 방문 손님(방문 1회)도 챙길 고객 탭에 오른다 — 안부(14일 안) · 다시 오실 때(표준 주기~두 배)."""
    cs = [
        {"id": "f1", "ext_id": "201", "revisit_state": "new", "last_visit": d(-6), "visit_count": 1},   # 안부
        {"id": "f2", "ext_id": "202", "revisit_state": "new", "last_visit": d(-40), "visit_count": 1},  # 뿌리염색 5주 지남
        {"id": "f3", "ext_id": "203", "revisit_state": "new", "last_visit": d(-40), "visit_count": 1},  # 펌 13주 전
        {"id": "f4", "ext_id": "204", "revisit_state": "new", "last_visit": d(-40), "visit_count": 1},  # 예약 있음
        {"id": "f5", "ext_id": "205", "revisit_state": "new", "last_visit": d(-6), "visit_count": 1},   # 연락함
    ]
    txs = [
        {"customer_id": "f1", "date": d(-6), "service": "여자컷", "kind": "service"},
        {"customer_id": "f2", "date": d(-40), "service": "뿌리염색", "kind": "service"},
        {"customer_id": "f2", "date": d(-40), "service": "선불충전", "kind": "charge"},   # 충전은 시술 아님
        {"customer_id": "f3", "date": d(-40), "service": "디지털펌", "kind": "service"},
        {"customer_id": "f4", "date": d(-40), "service": "뿌리염색", "kind": "service"},
    ]
    bks = [{"customer_id": "f4", "date": d(3), "time": "11:00", "status": "예약"}]
    m = up.measure(cs, txs, bks, {}, S, NOW, contacted={"f5"})
    assert m["care"] == 2 and m["care_first"] == (1, 1)     # f1 안부 · f2 다시 오실 때
    assert m["care_quiet"] == 1                              # f5 — 연락해서 잠시 빠짐
    lines = "\n".join(up.report("demo", "살롱", m))
    assert "그중 첫 방문    안부 1명 · 다시 오실 때 1명" in lines
