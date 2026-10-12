"""선불 손님 — web/lib/customers.ts prepaidAway(개선 계획 v5 P3).

통계 알약 '선불 3개월+ N명'과 눌러서 열리는 고객 목록 조건이 같은 함수라 숫자가 같다. 경계(90일 '넘게')와
이탈 표시·잔액 0·방문 기록 없음을 고정한다. TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

TODAY = "2026-10-12"
CASES = [
    ("잔액 · 91일 — 대상", {"prepaid_balance": 520000, "last_visit": "2026-07-13"}, True),
    ("잔액 · 딱 90일 — 아직", {"prepaid_balance": 520000, "last_visit": "2026-07-14"}, False),
    ("잔액 0", {"prepaid_balance": 0, "last_visit": "2026-01-01"}, False),
    ("잔액 음수(정정분)", {"prepaid_balance": -1000, "last_visit": "2026-01-01"}, False),
    ("이탈 표시", {"prepaid_balance": 300000, "last_visit": "2026-01-01", "churned_at": "2026-09-01T00:00:00Z"}, False),
    ("방문 기록 없음", {"prepaid_balance": 300000, "last_visit": None}, False),
    ("시각 붙은 날짜", {"prepaid_balance": 300000, "last_visit": "2026-07-01T00:00:00"}, True),
]


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/customers.ts"], """
const { prepaidAway, PREPAID_AWAY_DAYS } = require('./customers.js');
out({ days: PREPAID_AWAY_DAYS, got: D.cases.map((c) => prepaidAway(c, D.today)) });
""", {"cases": [c for _, c, _ in CASES], "today": TODAY})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_prepaid_away_rule(ts):
    assert ts["days"] == 90
    for (name, _, want), got in zip(CASES, ts["got"]):
        assert got is want, name
