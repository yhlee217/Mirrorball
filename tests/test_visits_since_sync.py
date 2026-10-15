"""방문 탭(web/lib/visits.ts) — 수집 뒤 지난 예약은 '예약 기준'으로, 'N회째'는 그 방문 당시 몇 번째.

2026-10-15 폰 확인: '어제 분명 손님이 계셨는데 방문에 없다' — 수집이 일요일 한 번이라 그 뒤 방문은 다음 일요일까지
기록이 없었다. 그리고 모든 줄에 지금 총 횟수를 붙여, 2주 안에 두 번 오신 분이 두 줄 다 같은 '7회째'였다.
TS 쪽은 tsc 로 컴파일해 node 로 돌린다(tests/tsnode.py). 도구가 없으면 건너뛴다.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from tsnode import run_ts

SYNC = {"date": "2026-10-12", "time": "14:05"}          # 마지막 수집(그날 14:05)
NOW = {"date": "2026-10-15", "time": "10:00"}           # 사흘 뒤 아침

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
    assert got["seen"] == {"a": {"count": 2, "last": "2026-10-14", "service": None}}
    assert got["none"] == 0                                          # 수집 기록이 없으면 세지 않는다
    assert got["later"] == ["2026-10-14", "2026-10-14", "2026-10-13", None]


def test_noshow_mark_and_undo_rules():
    """노쇼 표시 — 시간이 지난 예약만, 원래 상태를 남겨 되돌리기가 그대로 돌려놓는다. 표시한 예약은 방문으로 안 센다."""
    got = run_ts(["lib/visits.ts"], """
const { noShowUpdate, noShowsSinceSync, visitsSinceSync, seenSinceSync, isAppNoShow } = require('./visits.js');
const past = { date: '2026-10-14', time: '18:30', status: '예약' };
const marked = { ...past, status: noShowUpdate(past, false, D.now).status };
out({
  mark: noShowUpdate(past, false, D.now),
  markNull: noShowUpdate({ ...past, status: null }, false, D.now),
  future: noShowUpdate({ date: '2026-10-15', time: '15:00', status: '예약' }, false, D.now).ok,   // 아직 시간이 안 됨
  already: noShowUpdate({ ...past, status: '예약취소' }, false, D.now).ok,                         // 이미 취소
  undo: noShowUpdate(marked, true, D.now),
  undoNull: noShowUpdate({ ...past, status: '노쇼·앱|' }, true, D.now),
  undoHandsos: noShowUpdate({ ...past, status: '노쇼' }, true, D.now).ok,                         // HandSOS 노쇼는 앱이 못 돌린다
  isApp: [isAppNoShow(marked.status), isAppNoShow('노쇼'), isAppNoShow(null)],
  counted: visitsSinceSync([{ ...marked, customer_id: 'a' }], D.sync, D.now).length,
  seen: seenSinceSync([{ ...marked, customer_id: 'a' }], D.sync, D.now).size,
  listed: noShowsSinceSync([marked, past, { ...marked, date: '2026-10-10' }], D.sync, D.now).length,  // 수집 전 날은 빼고
});
""", {"sync": SYNC, "now": NOW})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["mark"] == {"ok": True, "status": "노쇼·앱|예약"}
    assert got["markNull"] == {"ok": True, "status": "노쇼·앱|"}
    assert got["future"] is False and got["already"] is False
    assert got["undo"] == {"ok": True, "status": "예약"}
    assert got["undoNull"] == {"ok": True, "status": None}
    assert got["undoHandsos"] is False
    assert got["isApp"] == [True, False, False]
    assert got["counted"] == 0 and got["seen"] == 0          # 표시하면 방문 · 횟수에서 빠진다
    assert got["listed"] == 1                                 # 방문 탭엔 줄을 그어 남긴다(되돌리기 자리)


def test_noshow_route_uses_the_same_rule():
    route = (Path(__file__).resolve().parent.parent / "web" / "app" / "api" / "booking-noshow" / "route.ts").read_text(encoding="utf-8")
    assert "noShowUpdate" in route and ".eq('tenant_id', tenantId)" in route and "getUser" in route


def test_seen_since_sync_keeps_the_latest_service():
    """홈 브리핑 '지난번' — 수집 뒤 다녀가신 방문이 마지막이면 그 예약(가장 늦은 것)의 시술."""
    got = run_ts(["lib/visits.ts"], """
const { seenSinceSync } = require('./visits.js');
out(Object.fromEntries([...seenSinceSync(D.rows, D.sync, D.now).entries()]));
""", {"sync": SYNC, "now": NOW, "rows": [
        {"customer_id": "a", "date": "2026-10-13", "time": "11:00", "status": "예약", "service": "커트"},
        {"customer_id": "a", "date": "2026-10-14", "time": "18:30", "status": "예약", "service": "뿌리염색"},
        {"customer_id": "a", "date": "2026-10-14", "time": "10:00", "status": "예약", "service": "클리닉"},
    ]})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got == {"a": {"count": 2, "last": "2026-10-14", "service": "뿌리염색"}}


def test_contact_effect_counts_visits_since_sync_as_came():
    """연락 효과(v9 P2) — 연락 뒤 예약 시간이 지나 다녀가신 분(예약 기준)도 '오심'. 날짜는 늘 날짜순."""
    got = run_ts(["lib/visits.ts", "lib/effect.ts"], """
const { withSeenVisits } = require('./visits.js');
const { contactEffect, helloEffect } = require('./effect.js');
const visits = new Map([['a', ['2026-09-01']], ['b', ['2026-08-01']], ['c', ['2026-10-01']]]);
const merged = withSeenVisits(visits, D.rows, D.sync, D.now);
out({
  merged: Object.fromEntries([...merged.entries()]),
  untouched: Object.fromEntries([...visits.entries()]),            // 원래 모음은 그대로
  noSync: Object.fromEntries([...withSeenVisits(visits, D.rows, null, D.now).entries()]),
  before: contactEffect(D.contacts, visits, new Set(['a']), '2026-10-01'),
  after: contactEffect(D.contacts, merged, new Set(['a']), '2026-10-01'),
  helloBefore: helloEffect(D.contacts, visits),
  helloAfter: helloEffect(D.contacts, merged),
});
""", {"sync": SYNC, "now": NOW, "rows": [
        {"customer_id": "a", "date": "2026-10-14", "time": "18:30", "status": "예약"},
        {"customer_id": "a", "date": "2026-10-14", "time": "19:00", "status": "예약"},   # 같은 날 — 한 번
        {"customer_id": "b", "date": "2026-10-13", "time": "12:00", "status": "노쇼"},   # 노쇼 — 안 셈
        {"customer_id": "c", "date": "2026-10-14", "time": "11:00", "status": "예약"},   # 순서가 뒤섞여 와도
        {"customer_id": "c", "date": "2026-10-13", "time": "11:00", "status": "예약"},   # 날짜순으로 넣는다
    ], "contacts": [
        {"customer_id": "a", "sent_at": "2026-10-13T01:00:00Z"},
        {"customer_id": "b", "sent_at": "2026-10-13T01:00:00Z"},
    ]})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["merged"] == {"a": ["2026-09-01", "2026-10-14"], "b": ["2026-08-01"],
                             "c": ["2026-10-01", "2026-10-13", "2026-10-14"]}
    assert got["untouched"] == {"a": ["2026-09-01"], "b": ["2026-08-01"], "c": ["2026-10-01"]}
    assert got["noSync"] == got["untouched"]
    assert got["before"] == {"contacted": 2, "came": 0, "booked": 1}    # 수집 기준 — a 는 '예약'으로만
    assert got["after"] == {"contacted": 2, "came": 1, "booked": 0}     # 지금 기준 — a 는 '오심'
    # 첫 방문 안부 효과(통계)는 첫째 · 둘째 방문을 앞에서 읽는다 — c(10.01 첫 방문)는 수집 뒤 다시 오셨다
    assert got["helloBefore"]["unsent"] == {"n": 1, "back": 0}
    assert got["helloAfter"]["unsent"] == {"n": 1, "back": 1}
