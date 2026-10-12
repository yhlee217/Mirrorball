"""이번 달 마감 예상 — web/lib/forecast.ts.

'이 속도면' = 지금까지 매출 + 시술 매출의 영업일 하루 평균 × 남은 영업일. 충전은 속도에 넣지 않고,
휴무는 영업일에서 빼고, 범위는 지난 6개월 같은 날짜 시점의 예상이 실제와 어긋난 폭으로 낸다.
TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import calendar
import datetime as dt

import pytest

from tsnode import run_ts

NO_OFF = {"off_weekdays": [], "off_dates": []}
TUE_OFF = {"off_weekdays": [1], "off_dates": []}


def svc(date, amt=100_000):
    return {"date": date, "kind": "service", "service": "여자컷", "amount_won": amt, "covered_won": 0}


def span(ym, d1, d2, amt=100_000, skip_weekday=None):
    y, m = map(int, ym.split("-"))
    out = []
    for d in range(d1, d2 + 1):
        day = dt.date(y, m, d)
        if skip_weekday is not None and day.weekday() == skip_weekday:
            continue
        out.append(svc(day.isoformat(), amt))
    return out


def mlen(ym):
    y, m = map(int, ym.split("-"))
    return calendar.monthrange(y, m)[1]


# A — 10.1~10.11 하루 10만원 + 10.3 선불 충전 100만원
CASE_A = span("2026-10", 1, 11) + [{"date": "2026-10-03", "kind": "charge", "service": "선불충전",
                                    "amount_won": 1_000_000, "covered_won": 0}]
# B — 화요일 휴무(10.6 화요일엔 매출 없음)
CASE_B = span("2026-10", 1, 11, skip_weekday=1)
# C — 지난 6개월: 11일까지는 하루 10만원, 그 뒤는 달마다 다른 속도 → 같은 시점 예상이 어긋난 폭
RATES = {"2026-04": 100_000, "2026-05": 110_000, "2026-06": 120_000,
         "2026-07": 90_000, "2026-08": 100_000, "2026-09": 130_000}
CASE_C = span("2026-10", 1, 11)
for ym, r in RATES.items():
    CASE_C += span(ym, 1, 11) + span(ym, 12, mlen(ym), r)

SCRIPT = """
const F = require('./forecast.js');
const run = (k) => {
  const c = D.cases[k];
  return F.monthForecast(c.tx, c.ym, c.asOf, c.off, new Set(c.tx.filter((t) => t.kind === 'service').map((t) => t.date)));
};
out(Object.fromEntries(Object.keys(D.cases).map((k) => [k, run(k)])));
"""


@pytest.fixture(scope="module")
def ts():
    cases = {
        "A": {"tx": CASE_A, "ym": "2026-10", "asOf": "2026-10-11", "off": NO_OFF},
        "B": {"tx": CASE_B, "ym": "2026-10", "asOf": "2026-10-11", "off": TUE_OFF},
        "C": {"tx": CASE_C, "ym": "2026-10", "asOf": "2026-10-11", "off": NO_OFF},
        "early": {"tx": span("2026-10", 1, 4), "ym": "2026-10", "asOf": "2026-10-04", "off": NO_OFF},
        "stale": {"tx": CASE_C, "ym": "2026-10", "asOf": "2026-09-27", "off": NO_OFF},
    }
    got = run_ts(["lib/forecast.ts"], SCRIPT, {"cases": cases})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_charges_are_added_not_extrapolated(ts):
    a = ts["A"]
    # 지금까지 210만(시술 110만 + 충전 100만) + 시술 하루 10만 × 남은 20일 = 410만
    assert a["soFar"] == 2_100_000 and a["worked"] == 11 and a["remaining"] == 20
    assert a["center"] == pytest.approx(4_100_000)
    assert a["low"] is None and a["high"] is None and a["months"] == 0   # 지난 달 기록이 없으면 범위 없음
    assert a["show"] is True


def test_off_days_are_not_counted_as_working_days(ts):
    b = ts["B"]
    # 영업 10일(10.6 화 휴무), 남은 날 20일 중 화요일 3번(13·20·27) 빼고 17일 → 100만 + 10만 × 17
    assert b["worked"] == 10 and b["remaining"] == 17
    assert b["center"] == pytest.approx(2_700_000)


def test_range_from_last_six_months(ts):
    c = ts["C"]
    pred = 1_100_000 + 100_000 * 20
    errs = []
    for ym, r in RATES.items():
        rest = mlen(ym) - 11
        p = 1_100_000 + 100_000 * rest
        errs.append((1_100_000 + r * rest - p) / p)
    errs.sort()
    assert c["months"] == 6
    assert c["center"] == pytest.approx(pred * (1 + errs[3]))   # 어긋남의 가운데로 바로잡는다
    assert c["low"] == pytest.approx(pred * (1 + errs[0]))
    assert c["high"] == pytest.approx(pred * (1 + errs[-1]))
    assert c["low"] < c["center"] < c["high"]
    assert c["lastMonth"] == 1_100_000 + 130_000 * 19              # 9월 전체


def test_hidden_until_five_working_days(ts):
    assert ts["early"]["show"] is False and ts["early"]["worked"] == 4


def test_no_data_this_month_yet(ts):
    s = ts["stale"]
    assert s["show"] is False and s["soFar"] == 0 and s["worked"] == 0
