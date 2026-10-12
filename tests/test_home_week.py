"""홈 '이번 주 요약'과 '예약 브리핑'의 계산 — web/lib/week.ts · web/lib/briefing.ts.

화면에 바로 숫자로 나가는 것들이라 경계(수집일·같은 날 두 건·선불 결제·워크인)를 사례로 고정한다.
TS 는 tsc → node 로 실행한다(tests/tsnode.py). 도구가 없으면 건너뛴다.
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

SYNC = "2026-10-11"      # 일요일 14:00 수집
TODAY = "2026-10-12"     # 월요일

# 지난 한 주 = 수집일 전날까지 7일(10.4 일 ~ 10.10 토), 전주 = 9.27 ~ 10.3
TX = [
    {"customer_id": "A", "date": "2026-10-05", "kind": "service", "service": "여자컷", "amount_won": 50000, "covered_won": 0},
    # 같은 날 두 번째 시술 — 방문은 한 번
    {"customer_id": "A", "date": "2026-10-05", "kind": "service", "service": "뿌리염색", "amount_won": 30000, "covered_won": 0},
    # 충전만 한 날 — 매출엔 들어가지만 방문은 아니다
    {"customer_id": "A", "date": "2026-10-06", "kind": "charge", "service": "선불충전", "amount_won": 300000, "covered_won": 0},
    # 선불 잔액으로 결제 — 방문이지만 실매출은 0(충전 때 이미 셌다)
    {"customer_id": "B", "date": "2026-10-08", "kind": "service", "service": "펌", "amount_won": 100000, "covered_won": 100000},
    # 워크인 집계 손님도 방문·매출에 든다
    {"customer_id": "W", "date": "2026-10-09", "kind": "service", "service": "남자컷", "amount_won": 20000, "covered_won": 0},
    # 고객 연결이 없는 거래 — 매출만
    {"customer_id": None, "date": "2026-10-09", "kind": "product", "service": "샴푸", "amount_won": 10000, "covered_won": 0},
    # 같은 주에 두 번 오면 두 번
    {"customer_id": "A", "date": "2026-10-10", "kind": None, "service": "앞머리컷", "amount_won": 5000, "covered_won": None},
    # 수집일 당일 — 수집 시각 뒤가 빠져 있어 지난 한 주에 넣지 않는다
    {"customer_id": "D", "date": "2026-10-11", "kind": "service", "service": "여자컷", "amount_won": 40000, "covered_won": 0},
    # 전주
    {"customer_id": "C", "date": "2026-10-03", "kind": "service", "service": "여자컷", "amount_won": 40000, "covered_won": 0},
]
FIRSTS = ["2026-10-05", "2026-10-03", "2026-10-11", None]

SCRIPT = """
const W = require('./week.js');
const B = require('./briefing.js');
const wk = W.lastWeek(D.sync, D.today);
out({
  add: [W.addDays('2026-10-11', -1), W.addDays('2026-03-01', -1), W.addDays('2026-01-01', -1), W.addDays('2026-12-31', 1)],
  wk, nosync: W.lastWeek(null, D.today),
  label: W.spanLabel(wk.cur),
  cur: W.weekNums(D.tx, D.firsts, wk.cur),
  prev: W.weekNums(D.tx, D.firsts, wk.prev),
  between: B.daysBetween('2026-09-01', '2026-10-13'),
  words: D.words.map(B.spanWords),
  gaps: D.gaps.map((g) => B.gapLine(g[0], g[1], g[2])),
  // 7.1 → 10.13(104일)이지만 그 사이 휴가 53일(7.10~8.31) → 51일, 평소 35일의 1.6배(56) 안
  gapVac: B.gapLine('2026-07-01', '2026-10-13', 35, { off_weekdays: [], off_dates: [{ from: '2026-07-10', to: '2026-08-31' }] }),
  tags: [B.visitTag(0), B.visitTag(null), B.visitTag(1), B.visitTag(5)],
  memo: [B.memoLines(D.pref, 2), B.memoLines(null, 2), B.memoLines('  \\n- \\n', 2)],
  recent: [B.latestRecent(D.recent), B.latestRecent('- 강아지 키움'), B.latestRecent(null)],
  last: Object.fromEntries(B.lastServices(D.lastTx, (id) => D.lastVisit[id])),
  heads: ['2026-10-12', '2026-10-13', '2026-10-15'].map((d) => B.dayHead(d, D.today)),
});
"""

WORDS = [10, 13, 14, 42, 69, 70, 90, 400, 729, 730]
GAPS = [
    ["2026-09-01", "2026-10-13", 35],     # 42일, 평소 35일 → 늦지 않음(56일까지)
    ["2026-07-01", "2026-10-13", 35],     # 104일 → 평소의 1.6배를 넘음
    ["2026-09-01", "2026-10-13", None],   # 1회 방문 — 평소 주기 없음
    [None, "2026-10-13", 35],             # 첫 방문
    ["2026-10-13", "2026-10-13", 35],     # 같은 날 — 말이 안 된다
]
PREF = "- 두피 예민\n- 뿌리 볼륨 선호\n- 앞머리 짧게 싫어함"
RECENT = "- (2026-05) 이사 준비\n- (2026-08) 딸 결혼\n- (2026-07) 제주 여행"
LAST_TX = [
    {"customer_id": "A", "date": "2026-09-01", "service": "여자컷(원장)", "kind": "service"},
    {"customer_id": "A", "date": "2026-09-01", "service": "뿌리염색", "kind": "service"},
    {"customer_id": "A", "date": "2026-09-01", "service": "선불충전", "kind": "charge"},
    {"customer_id": "A", "date": "2026-07-01", "service": "펌", "kind": "service"},      # 더 예전 방문
    {"customer_id": "B", "date": "2026-09-01", "service": "펌", "kind": "service"},      # B 의 마지막 방문일이 아님
]
LAST_VISIT = {"A": "2026-09-01", "B": "2026-09-20"}


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/week.ts", "lib/briefing.ts"], SCRIPT, {
        "sync": SYNC, "today": TODAY, "tx": TX, "firsts": FIRSTS, "words": WORDS, "gaps": GAPS,
        "pref": PREF, "recent": RECENT, "lastTx": LAST_TX, "lastVisit": LAST_VISIT,
    })
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_add_days_crosses_month_and_year(ts):
    assert ts["add"] == ["2026-10-10", "2026-02-28", "2025-12-31", "2027-01-01"]


def test_last_week_ends_the_day_before_sync(ts):
    """수집일 당일은 수집 시각 뒤가 비어 있다 → 전날까지 7일. 전주도 같은 모양."""
    assert ts["wk"] == {"cur": {"start": "2026-10-04", "end": "2026-10-10"},
                        "prev": {"start": "2026-09-27", "end": "2026-10-03"}}
    assert ts["label"] == "10.4(일)~10.10(토)"


def test_last_week_without_sync_record_ends_yesterday(ts):
    assert ts["nosync"]["cur"] == {"start": "2026-10-05", "end": "2026-10-11"}


def test_week_numbers(ts):
    # 방문: A 10.5(두 건이 한 번) · B 10.8 · W 10.9 · A 10.10 = 4. 충전만 한 날·연결 없는 거래·수집일은 빠짐
    # 매출: 5만+3만+충전 30만+선불결제 0+2만+샴푸 1만+5천 = 41.5만. 수집일(10.11)은 빠짐
    assert ts["cur"] == {"visits": 4, "firsts": 1, "revenue": 415000}
    assert ts["prev"] == {"visits": 1, "firsts": 1, "revenue": 40000}


def test_span_words(ts):
    assert ts["between"] == 42
    assert ts["words"] == ["10일", "13일", "2주", "6주", "10주", "2개월", "3개월", "13개월", "24개월", "2년"]


def test_gap_line(ts):
    assert ts["gaps"] == [
        {"text": "6주 만 · 평소 5주", "late": False},
        {"text": "3개월 만 · 평소 5주", "late": True},
        {"text": "6주 만", "late": False},
        None,
        None,
    ]


def test_gap_line_late_skips_vacation(ts):
    """'몇 주 만'은 달력 그대로, 늦었는지는 휴가를 빼고 — 챙길 고객과 같은 기준."""
    assert ts["gapVac"] == {"text": "3개월 만 · 평소 5주", "late": False}


def test_visit_tag(ts):
    assert ts["tags"] == ["첫 방문", "첫 방문", "두 번째 방문", None]


def test_memo_lines(ts):
    assert ts["memo"] == [["두피 예민", "뿌리 볼륨 선호"], [], []]


def test_latest_recent_picks_newest_month(ts):
    """근황은 (YYYY-MM) 꼬리표로 가장 최근 것을 고른다 — 줄 순서에 기대지 않는다."""
    assert ts["recent"] == ["(2026-08) 딸 결혼", "강아지 키움", None]


def test_last_services_only_last_visit_day_services(ts):
    """마지막 방문일의 시술만 — 충전·예전 방문·다른 날 거래는 빠진다. 직급 표기는 뗀다."""
    assert ts["last"] == {"A": "커트 + 뿌리염색"}


def test_day_heads(ts):
    assert ts["heads"] == ["오늘 · 10.12(월)", "내일 · 10.13(화)", "10.15(목)"]
