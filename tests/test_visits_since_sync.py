"""방문 탭(web/lib/visits.ts) — 수집 뒤 지난 예약은 '예약 기준'으로, 'N회째'는 그 방문 당시 몇 번째.

2026-10-15 폰 확인: '어제 분명 손님이 계셨는데 방문에 없다' — 수집이 일요일 한 번이라 그 뒤 방문은 다음 일요일까지
기록이 없었다. 그리고 모든 줄에 지금 총 횟수를 붙여, 2주 안에 두 번 오신 분이 두 줄 다 같은 '7회째'였다.
TS 쪽은 tsc 로 컴파일해 node 로 돌린다(tests/tsnode.py). 도구가 없으면 건너뛴다.
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

SYNC = {"date": "2026-10-12", "time": "14:05"}          # 일요일 수집
NOW = {"date": "2026-10-15", "time": "10:00"}           # 수요일 아침

BOOKINGS = [
    {"id": "sun-am", "date": "2026-10-12", "time": "11:00", "status": "예약"},     # 수집 전 시각 — 이미 수집됨
    {"id": "sun-pm", "date": "2026-10-12", "time": "16:00", "status": "예약"},     # 수집 뒤 — 예약 기준
    {"id": "sun-nt", "date": "2026-10-12", "time": None, "status": "예약"},        # 시각 모름 — 수집된 것으로
    {"id": "mon", "date": "2026-10-13", "time": "12:00", "status": None},          # 예약 기준
    {"id": "tue-no", "date": "2026-10-14", "time": "15:00", "status": "노쇼"},     # 노쇼 — 뺀다
    {"id": "tue-cx", "date": "2026-10-14", "time": "17:00", "status": "예약취소"}, # 취소 — 뺀다
    {"id": "tue", "date": "2026-10-14", "time": "18:30", "status": "예약"},        # 어제 — 예약 기준
    {"id": "wed-am", "date": "2026-10-15", "time": "09:30", "status": "예약"},     # 오늘 이미 지남 — 예약 기준
    {"id": "wed-pm", "date": "2026-10-15", "time": "15:00", "status": "예약"},     # 오늘 아직 — 아직 방문 아님
    {"id": "old", "date": "2026-10-10", "time": "12:00", "status": "예약"},        # 수집 전 날 — 이미 수집됨
]


def _run():
    return run_ts(["lib/visits.ts"], """
const { visitOrdinals, visitsSinceSync } = require('./visits.js');
const total = { a: 7, b: 1, c: 3 };
const ord = visitOrdinals(D.visits, (id) => total[id]);
out({
  pending: visitsSinceSync(D.bookings, D.sync, D.now).map((b) => b.id),
  ord: Object.fromEntries([...ord.entries()]),
});
""", {"bookings": BOOKINGS, "sync": SYNC, "now": NOW, "visits": [
        {"customer_id": "a", "date": "2026-10-01"}, {"customer_id": "a", "date": "2026-10-09"},
        {"customer_id": "a", "date": "2026-10-09"},                       # 같은 날 두 줄 — 한 방문
        {"customer_id": "b", "date": "2026-10-11"},
        {"customer_id": "c", "date": "2026-10-03"}, {"customer_id": "c", "date": "2026-10-10"},
        {"customer_id": "c", "date": "2026-10-12"},
    ]})


def test_bookings_after_sync_show_as_visits_until_next_sync():
    got = _run()
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["pending"] == ["sun-pm", "mon", "tue", "wed-am"]


def test_visit_number_is_as_of_that_visit():
    got = _run()
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    # a: 지금 7회 — 10.09 가 7회째, 10.01 이 6회째(전에는 둘 다 '7회째')
    assert got["ord"]["a|2026-10-09"] == 7 and got["ord"]["a|2026-10-01"] == 6
    assert got["ord"]["b|2026-10-11"] == 1                               # 첫 방문
    assert [got["ord"][f"c|2026-10-{d}"] for d in ("12", "10", "03")] == [3, 2, 1]


def test_seen_since_sync_counts_each_customer_as_of_now():
    """고객 목록 · 상세보기 — 지금 기준으로 다녀가신 분은 'N회' · 마지막 방문에 바로 센다(같은 날 두 예약은 한 번)."""
    got = run_ts(["lib/visits.ts"], """
const { seenSinceSync, laterDay } = require('./visits.js');
const m = seenSinceSync(D.rows, D.sync, D.now);
out({
  seen: Object.fromEntries([...m.entries()]),
  none: seenSinceSync(D.rows, null, D.now).size,
  later: [laterDay('2026-07-01', '2026-10-14'), laterDay('2026-10-14T05:00:00Z', null), laterDay(null, '2026-10-13'), laterDay(null, null)],
});
""", {"sync": SYNC, "now": NOW, "rows": [
        {"customer_id": "a", "date": "2026-10-13", "time": "11:00", "status": "예약"},
        {"customer_id": "a", "date": "2026-10-14", "time": "18:30", "status": "예약"},
        {"customer_id": "a", "date": "2026-10-14", "time": "19:30", "status": "예약"},    # 같은 날 두 예약 — 한 번
        {"customer_id": "b", "date": "2026-10-14", "time": "15:00", "status": "노쇼"},    # 노쇼 — 안 셈
        {"customer_id": "c", "date": "2026-10-15", "time": "15:00", "status": "예약"},    # 아직 안 옴 — 안 셈
        {"customer_id": "d", "date": "2026-10-12", "time": "11:00", "status": "예약"},    # 수집 전 — 이미 수집됨
        {"customer_id": None, "date": "2026-10-14", "time": "12:00", "status": "예약"},   # 손님 기록 없음
    ]})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["seen"] == {"a": {"count": 2, "last": "2026-10-14"}}
    assert got["none"] == 0                                          # 수집 기록이 없으면 세지 않는다
    assert got["later"] == ["2026-10-14", "2026-10-14", "2026-10-13", None]
