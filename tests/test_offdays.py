"""휴무 — 설정 저장 형식(web/lib/settings.ts)과 영업일 계산(web/lib/offdays.ts).

설정은 디자이너가 직접 고치는 값이라 이상한 값(겹치는 기간, 거꾸로 넣은 기간, 없는 날짜)이 들어와도
같은 모양으로 정리돼야 한다. 영업일은 '쉬기로 정한 날이 아니거나, 정했어도 방문이 있었던 날'.
TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

RAW = {
    "vip_won": 2000000,
    "lapsed_months": -3,                     # 음수 → 기본값
    "off_weekdays": [6, 1, 1, 9, -1, 2.5, "3"],
    "off_dates": [
        {"from": "2026-09-10", "to": "2026-09-05"},   # 거꾸로 → 뒤집는다
        {"from": "2026-09-08", "to": "2026-09-12"},   # 겹친다 → 9.5~9.12 하나로
        {"from": "2026-09-13", "to": "2026-09-13"},   # 맞닿는다 → 9.5~9.13
        {"from": "2026-02-30", "to": "2026-03-01"},   # 없는 날짜 → 버린다
        {"from": "2026-07-01", "to": "2026-07-03"},
        {"from": "x", "to": "2026-07-03"},
        None,
    ],
}
MANY = [{"from": f"2025-{m:02d}-{d:02d}", "to": f"2025-{m:02d}-{d:02d}"} for m in range(1, 13) for d in (1, 10, 20, 25, 28, 5)]

OFF = {"off_weekdays": [1], "off_dates": [{"from": "2026-10-08", "to": "2026-10-09"}]}   # 화 휴무 + 10.8~9 휴가

SCRIPT = """
const S = require('./settings.js');
const O = require('./offdays.js');
const merged = S.mergeSettings(D.raw);
const many = S.mergeSettings({ off_dates: D.many }).off_dates;
out({
  merged: { vip_won: merged.vip_won, lapsed_months: merged.lapsed_months, off_weekdays: merged.off_weekdays, off_dates: merged.off_dates },
  junk: [S.mergeSettings(null).off_weekdays, S.mergeSettings({ off_dates: 'x', off_weekdays: 3 }).off_dates],
  many: [many.length, many[0], many[many.length - 1]],
  off: ['2026-10-13', '2026-10-14', '2026-10-08', '2026-10-10'].map((d) => O.isOffDay(d, D.off)),
  has: [O.hasOffDays(D.off), O.hasOffDays({ off_weekdays: [], off_dates: [] })],
  // 10.5(월)~10.11(일): 화(10.6) 휴무, 10.8~9 휴가 → 4일. 10.9 에 방문이 있으면 그날은 영업한 날 → 5일
  worked: [O.workedDays('2026-10-05', '2026-10-11', D.off, new Set()), O.workedDays('2026-10-05', '2026-10-11', D.off, new Set(['2026-10-09']))],
  byDow: O.workedByWeekday('2026-10-05', '2026-10-18', D.off, new Set()),
  ends: [
    O.windowEnd('2026-06-20', 90, { off_weekdays: [1], off_dates: [] }),                                  // 휴가 없음 → 90일
    O.windowEnd('2026-06-20', 90, { off_weekdays: [], off_dates: [{ from: '2026-07-01', to: '2026-07-14' }] }),   // 14일 휴가 → 104일
    O.windowEnd('2026-06-20', 90, { off_weekdays: [], off_dates: [{ from: '2026-09-15', to: '2026-09-30' }] }),   // 늘린 구간에 또 걸린다
    O.windowEnd('2026-06-20', 90, { off_weekdays: [], off_dates: [{ from: '2026-06-01', to: '2026-06-20' }] }),   // 시작 전·당일 휴가는 무관
  ],
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/settings.ts", "lib/offdays.ts"], SCRIPT, {"raw": RAW, "many": MANY, "off": OFF})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_settings_keep_numbers_and_clean_weekdays(ts):
    m = ts["merged"]
    assert m["vip_won"] == 2000000 and m["lapsed_months"] == 12      # 잘못된 숫자는 기본값
    assert m["off_weekdays"] == [1, 6]                                # 0~6 정수만, 중복 없이 정렬


def test_settings_merge_and_clean_vacations(ts):
    assert ts["merged"]["off_dates"] == [
        {"from": "2026-07-01", "to": "2026-07-03"},
        {"from": "2026-09-05", "to": "2026-09-13"},                   # 거꾸로·겹침·맞닿음이 하나로
    ]
    assert ts["junk"] == [[], []]


def test_settings_cap_vacation_count(ts):
    n, first, last = ts["many"]
    assert n == 60 and last == {"from": "2025-12-28", "to": "2025-12-28"}   # 오래된 것부터 버린다
    assert first["from"] > "2025-01-28"


def test_is_off_day(ts):
    # 10.13 화(정기 휴무) · 10.14 수 · 10.8 휴가 · 10.10 토
    assert ts["off"] == [True, False, True, False]
    assert ts["has"] == [True, False]


def test_worked_days_counts_visited_off_days(ts):
    assert ts["worked"] == [4, 5]
    # 10.5~10.18 두 주: 화요일 둘 다 휴무, 휴가가 목(10.8)·금(10.9)에 하루씩
    assert ts["byDow"] == [2, 0, 2, 1, 1, 2, 2]


def test_window_end_stretches_only_for_vacations(ts):
    assert ts["ends"] == ["2026-09-18", "2026-10-02", "2026-10-04", "2026-09-18"]
