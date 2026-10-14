"""수집 뒤 지난 예약(개선 계획 v6 P0) — 웹(lib/bookings bookingSets)과 점검 스크립트(ux_probe care_hold)가 같은 분을 뺀다.

일요일 수집 때 화요일 예약이던 분은 수요일부터 예약이 '지난 것'이 되는데, 그날 방문은 다음 수집에야 잡힌다.
그 사이 챙길 고객에 다시 오르면 어제 오신 분께 '오랜만이에요'가 나간다 → 다음 수집까지 '다녀가셨을 분'으로 뺀다.
TS 쪽은 tsc 로 컴파일해 node 로 돌린다(tests/tsnode.py). 도구가 없으면 그 테스트만 건너뛴다.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import ux_probe as up  # noqa: E402

NOW = dt.datetime(2026, 10, 14, 15, 0, tzinfo=up.KST)  # 수요일 15시
TODAY = NOW.date()
SINCE = "2026-10-11"                                     # 일요일 수집
S = up.lapse_settings(None)


def d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


ROWS = [
    {"customer_id": "up", "date": d(3), "time": "11:00", "status": "예약"},          # 앞으로 올 예약
    {"customer_id": "tue", "date": d(-1), "time": "12:00", "status": "예약"},        # 수집 뒤 지난 예약 → 다녀가셨을 분
    {"customer_id": "am", "date": d(0), "time": "10:00", "status": None},            # 오늘, 이미 지난 시각
    {"customer_id": "sun", "date": SINCE, "time": "17:00", "status": "예약"},         # 수집한 날
    {"customer_id": "noshow", "date": d(-1), "time": "12:00", "status": "노쇼"},     # 노쇼 → 계속 챙길 분
    {"customer_id": "cancel", "date": d(2), "time": "12:00", "status": "예약취소"},   # 취소
    {"customer_id": "old", "date": "2026-10-09", "time": "12:00", "status": "예약"},  # 수집 전 — 방문은 이미 잡혔다
    {"customer_id": None, "date": d(1), "time": "12:00", "status": "예약"},            # 손님 미연결
]


def test_hold_is_upcoming_plus_passed_since_sync():
    assert up.care_hold(ROWS, SINCE, NOW) == {"up", "tue", "am", "sun"}


def test_web_and_probe_hold_the_same_people():
    got = run_ts(["lib/bookings.ts"], """
const { bookingSets } = require('./bookings.js');
const s = bookingSets(D.rows, D.since, D.now);
out({ upcoming: [...s.upcoming].sort(), hold: [...s.hold].sort() });
""", {"rows": ROWS, "since": SINCE, "now": {"date": TODAY.isoformat(), "time": "15:00"}})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["hold"] == sorted(up.care_hold(ROWS, SINCE, NOW))
    # '예약 있음'(고객 목록)은 앞으로 올 예약만 — 지난 예약은 '다녀가셨을 분'일 뿐 예약이 아니다
    assert got["upcoming"] == ["up"]
    assert got["upcoming"] == sorted(b["customer_id"] for b in ROWS if b["customer_id"] and up.is_active_booking(b, NOW))


def test_customer_seen_since_sync_leaves_the_list_until_next_sync():
    c = [{"id": "tue", "ext_id": "301", "revisit_state": "overdue", "last_visit": "2026-07-01", "visit_count": 5,
          "first_visit": "2025-01-01", "revisit_cycle_days": 35}]
    bks = [{"customer_id": "tue", "date": d(-1), "time": "12:00", "status": "예약"}]
    # 일요일 수집 뒤 화요일 예약이 지났다 — 다녀가셨을 분이라 목록 밖
    m = up.measure(c, [], bks, {}, S, NOW, since=SINCE)
    assert m["care"] == 0 and m["care_booked"] == 1
    # 다음 수집이 노쇼로 고쳐 받아 오면 다시 오른다(그 예약은 이제 수집일보다 앞)
    m = up.measure(c, [], [{**bks[0], "status": "노쇼"}], {}, S, NOW + dt.timedelta(days=5), since="2026-10-18")
    assert m["care"] == 1
    # 수집일을 모르면 오늘부터만 본다 — 지난 예약은 못 가린다(전과 같다)
    assert up.measure(c, [], bks, {}, S, NOW)["care"] == 1


def test_carte_next_says_passed_booking_instead_of_overdue():
    """카르테 '다음' 칸 — 예약 > 지난 예약 > 예상. 지난 예약이면 '5주 지남'을 셈하지 않는다."""
    got = run_ts(["lib/carte-stats.ts"], """
const { nextVisit } = require('./carte-stats.js');
const base = { today: '2026-10-14', lastVisit: '2026-07-01', visitCount: 5, cycleDays: 35, lastServices: ['뿌리염색'] };
out([
  nextVisit({ ...base, bookedDate: '2026-10-20', passedDate: '2026-10-13' }),
  nextVisit({ ...base, bookedDate: null, passedDate: '2026-10-13' }),
  nextVisit({ ...base, bookedDate: null, passedDate: null }).kind,
]);
""", {})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got[0] == {"kind": "booked", "date": "2026-10-20"}
    assert got[1] == {"kind": "passed", "date": "2026-10-13"}
    assert got[2] == "expected"
