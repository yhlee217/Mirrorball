"""카르테 숫자 타일 — web/lib/carte-stats.ts (다음 방문 · 매출 순위 · '며칠 전').

다음 방문은 실측(평소 주기)과 추정(시술 표준 주기)이 섞이는 자리라, 어느 쪽을 썼는지가
화면 문구에 그대로 드러나야 한다. 사례로 고정한다. TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

TODAY = "2026-10-12"

NEXT = [
    # 잡힌 예약이 있으면 그게 답
    {"today": TODAY, "lastVisit": "2026-09-19", "visitCount": 5, "cycleDays": 35,
     "lastServices": ["뿌리염색"], "bookedDate": "2026-10-14"},
    # 2회 이상 — 평소 주기(실측)
    {"today": TODAY, "lastVisit": "2026-09-19", "visitCount": 5, "cycleDays": 35,
     "lastServices": ["뿌리염색"], "bookedDate": None},
    # 2회 이상 — 예상일이 지났다
    {"today": TODAY, "lastVisit": "2026-08-01", "visitCount": 5, "cycleDays": 35,
     "lastServices": ["뿌리염색"], "bookedDate": None},
    # 1회 — 그날 시술 중 가장 짧은 표준 주기(여자커트 56 · 뿌리염색 35 → 35), 추정
    {"today": TODAY, "lastVisit": "2026-09-19", "visitCount": 1, "cycleDays": None,
     "lastServices": ["여자컷(원장)", "뿌리염색"], "bookedDate": None},
    # 1회 — 맞는 시술이 없으면 42일, 그냥 '추정'
    {"today": TODAY, "lastVisit": "2026-09-19", "visitCount": 1, "cycleDays": None,
     "lastServices": ["선불충전"], "bookedDate": None},
    # 방문 기록 없음
    {"today": TODAY, "lastVisit": None, "visitCount": 0, "cycleDays": None,
     "lastServices": [], "bookedDate": None},
    # 2회 이상인데 주기가 비어 있으면(재계산 전) 시술 기준으로 추정
    {"today": TODAY, "lastVisit": "2026-09-19", "visitCount": 3, "cycleDays": None,
     "lastServices": ["남자컷"], "bookedDate": None},
]
RANKS = [[0, 1000], [49, 1000], [50, 1000], [6, 100], [999, 1000], [0, 0], [5, 5], [-1, 10]]

SCRIPT = """
const S = require('./carte-stats.js');
out({
  ago: [0, 1, 5, 23, 100].map(S.agoWords),
  short: S.shortDate('2026-10-20'),
  next: D.next.map(S.nextVisit),
  ranks: D.ranks.map((r) => S.rankPercent(r[0], r[1])),
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/carte-stats.ts"], SCRIPT, {"next": NEXT, "ranks": RANKS})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_ago_words(ts):
    assert ts["ago"] == ["오늘", "어제", "5일 전", "3주 전", "3개월 전"]
    assert ts["short"] == "10.20"


def test_next_visit_booked_wins(ts):
    assert ts["next"][0] == {"kind": "booked", "date": "2026-10-14"}


def test_next_visit_from_personal_cycle(ts):
    assert ts["next"][1] == {"kind": "expected", "date": "2026-10-24", "basis": "평소 5주 주기",
                             "estimated": False, "overdueDays": 0}


def test_next_visit_overdue(ts):
    # 8.1 + 35일 = 9.5, 오늘(10.12)까지 37일 지남
    assert ts["next"][2] == {"kind": "expected", "date": "2026-09-05", "basis": "평소 5주 주기",
                             "estimated": False, "overdueDays": 37}


def test_next_visit_one_visit_uses_shortest_service_cycle(ts):
    assert ts["next"][3] == {"kind": "expected", "date": "2026-10-24", "basis": "뿌리염색 기준 추정",
                             "estimated": True, "overdueDays": 0}


def test_next_visit_unknown_service_falls_back_to_42_days(ts):
    assert ts["next"][4] == {"kind": "expected", "date": "2026-10-31", "basis": "추정",
                             "estimated": True, "overdueDays": 0}


def test_next_visit_without_history(ts):
    assert ts["next"][5] is None


def test_next_visit_missing_cycle_is_estimated(ts):
    # 남자커트 표준 28일 → 9.19 + 28 = 10.17
    assert ts["next"][6] == {"kind": "expected", "date": "2026-10-17", "basis": "남자커트 기준 추정",
                             "estimated": True, "overdueDays": 0}


def test_rank_percent(ts):
    """1등도 1%, 경계는 올림, 6/100 같은 값이 부동소수 오차로 한 칸 밀리지 않는다."""
    assert ts["ranks"] == [1, 5, 6, 7, 100, None, None, None]
