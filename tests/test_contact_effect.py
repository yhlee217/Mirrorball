"""연락 효과 — web/lib/effect.ts (개선 계획 v4 P2).

연락한 뒤 오셨나를 사람 단위로 센다. 연락 시각은 UTC 로 저장되고 거래 날짜는 KST 라 날짜를 맞춰
견준다(자정 근처에 하루가 어긋나면 '그날 오신 분'이 빠진다). TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

VISITS = {
    "A": ["2026-06-01", "2026-08-01", "2026-10-20"],   # 2회 이상 · 10.12 연락 → 10.20 오심
    "B": ["2026-07-01", "2026-08-01"],   # 2회 이상 · 연락 뒤 안 옴 · 예약 있음
    "C": ["2026-10-01"],                 # 첫 방문 손님 · 10.13 안부 → 아직
    "D": ["2026-10-02", "2026-10-30"],   # 첫 방문 손님 · 10.13 안부 → 다시 오심
    "E": ["2026-10-03"],                 # 첫 방문 손님 · 연락 안 함
    "F": ["2026-10-04", "2026-10-09"],   # 첫 방문 손님 · 혼자 다시 오심 → 그 뒤 연락(안부 아님)
    "G": ["2026-05-01"],                 # 오래전 첫 방문 — 안부 비교 대상 아님
}
CONTACTS = [
    {"customer_id": "A", "sent_at": "2026-10-12T01:00:00Z"},
    {"customer_id": "A", "sent_at": "2026-10-14T01:00:00Z"},   # 같은 분 두 번 — 사람은 한 번
    {"customer_id": "B", "sent_at": "2026-10-12T02:00:00Z"},
    {"customer_id": "C", "sent_at": "2026-10-13T00:30:00Z"},
    # 10.12 23:30 KST = 10.12 14:30 UTC — KST 날짜로 10.12
    {"customer_id": "D", "sent_at": "2026-10-12T14:30:00Z"},
    {"customer_id": "F", "sent_at": "2026-10-20T03:00:00Z"},
    {"customer_id": "X", "sent_at": "2026-09-01T03:00:00Z"},   # 기간 밖(since 전)
    {"customer_id": None, "sent_at": "2026-10-12T03:00:00Z"},
]
BOOKED = ["B"]

SCRIPT = """
const E = require('./effect.js');
const visits = new Map(Object.entries(D.visits));
const booked = new Set(D.booked);
out({
  day: [E.kstDay('2026-10-12T14:59:00Z'), E.kstDay('2026-10-12T15:00:00Z')],
  eff: E.contactEffect(D.contacts, visits, booked, '2026-10-01'),
  groups: E.contactEffectByGroup(D.contacts, visits, booked),
  hello: E.helloEffect(D.contacts, visits, '2026-09-28'),
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/effect.ts"], SCRIPT, {"visits": VISITS, "contacts": CONTACTS, "booked": BOOKED})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_contact_day_is_kst(ts):
    assert ts["day"] == ["2026-10-12", "2026-10-13"]


def test_effect_counts_people_once(ts):
    # A·B·C·D·F 다섯 분(X 는 기간 밖) — 연락 뒤 오심 A·D, 예약 B. C 는 아직,
    # F 는 연락 '전에' 다시 왔다(연락 뒤 방문이 아니다)
    assert ts["eff"] == {"contacted": 5, "came": 2, "booked": 1}


def test_effect_by_group(ts):
    # 연락하던 때 방문 1회 = 첫 방문 손님(C·D), 2회 이상(A·B·F — F 는 혼자 다시 온 뒤 연락)
    assert ts["groups"]["first"] == {"contacted": 2, "came": 1, "booked": 0}
    assert ts["groups"]["repeat"] == {"contacted": 3, "came": 1, "booked": 1}


def test_hello_effect_compares_sent_and_unsent(ts):
    # 9.28 이후 첫 방문: C·D(안부) · E·F(안부 아님 — F 는 다시 온 뒤에 연락)
    assert ts["hello"] == {"sent": {"n": 2, "back": 1}, "unsent": {"n": 2, "back": 1}}
