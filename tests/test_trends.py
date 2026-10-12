"""통계 '변화' 계산 — web/lib/trends.ts (D2 신규 재방문 · D4 요일×시간대 · D5 시술별 · D3 활성 고객).

기준일(asOf)은 마지막 수집일이다. 기간 경계(90일)·진행 중인 달·워크인 집계·충전·시각 없는 방문을
사례로 고정한다. TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

AS_OF = "2026-10-11"   # 일요일 수집


def svc(cid, date, time=None, service="여자컷", amount=30000, kind="service"):
    return {"customer_id": cid, "date": date, "time": time, "kind": kind, "service": service, "amount_won": amount}


# D2 — 첫 방문 달별 90일 안에 다시
COHORT_TX = [
    svc("n1", "2026-06-05"), svc("n1", "2026-07-10"),     # 35일 만 → 6월 다시 옴
    svc("n2", "2026-06-20"), svc("n2", "2026-10-01"),     # 103일 만 → 90일 넘어 '다시 옴' 아님
    svc("n3", "2026-06-25"),                              # 안 옴
    svc("n4", "2026-09-03"), svc("n4", "2026-09-24"),     # 21일 만 → 9월(진행 중) 다시 옴
    svc("n5", "2026-03-15"),                              # 범위 밖(4~9월만)
    svc("n7", "2026-10-02"),                              # 이번 달 — 아직 세지 않는다
]
FIRSTS = [
    {"id": "n1", "first_visit": "2026-06-05"}, {"id": "n2", "first_visit": "2026-06-20"},
    {"id": "n3", "first_visit": "2026-06-25"}, {"id": "n4", "first_visit": "2026-09-03"},
    {"id": "n5", "first_visit": "2026-03-15"}, {"id": "n6", "first_visit": None},
    {"id": "n7", "first_visit": "2026-10-02"},
]

# D4 — 요일 × 시간대(2026-10-05 월 · 10-10 토)
HEAT_TX = [
    svc("A", "2026-10-05", "15:00"), svc("A", "2026-10-05", "10:00"),   # 같은 날 두 건 → 한 번, 이른 시각
    svc("B", "2026-10-10", "14:30"), svc("C", "2026-10-10", "14:00"),   # 토 14–16시 두 번
    svc("D", "2026-10-10", "19:10"),                                    # 토 18시~
    svc("E", "2026-10-06", None),                                       # 시각 없음
    svc("F", "2026-10-07", "9:05"),                                     # 한 자리 시각도 읽는다
    svc("G", "2026-03-01", "11:00"),                                    # 기간 밖
    svc("H", "2026-10-12", "11:00"),                                    # 수집일 뒤
    svc("I", "2026-10-08", "11:00", service="선불충전", kind="charge"),   # 충전은 방문 아님
    svc(None, "2026-10-08", "11:00"),                                   # 손님 연결 없음
]

# D5 — 시술별(최근 1년, 90일 다 지난 시술만 '다시 옴' 분모)
SVC_TX = [
    svc("R1", "2026-05-01", service="여자컷", amount=30000),     # 6.1 에 다시 → 다시 옴
    svc("R1", "2026-06-01", service="뿌리염색", amount=60000),   # 그 뒤 없음
    svc("R2", "2026-06-01", service="여자컷", amount=30000),     # 그 뒤 없음
    svc("R3", "2026-09-01", service="여자컷", amount=33000),     # 90일 안 지남 → 분모 제외
    svc("R2", "2026-06-01", service="선불충전", amount=300000, kind="charge"),
    svc("W", "2026-05-10", service="남자컷", amount=15000),      # 워크인 집계 — 분모 제외
    svc("W", "2026-05-20", service="남자컷", amount=15000),
    svc("R1", "2025-01-01", service="여자컷", amount=25000),     # 1년 전 — 기간 밖
]
REAL = ["R1", "R2", "R3"]

# 휴무 — 화요일 정기 휴무 + 7.1~7.14 휴가(14일). 토요일 하나(10.3)도 휴가
OFF = {"off_weekdays": [1], "off_dates": [{"from": "2026-07-01", "to": "2026-07-14"}, {"from": "2026-10-03", "to": "2026-10-03"}]}

SCRIPT = """
const T = require('./trends.js');
const W = require('./week.js');
const byC = (tx) => T.datesByCustomer(T.toVisits(tx));
const heatVisits = T.toVisits(D.heat);
const svcBy = byC(D.svc);
out({
  visitsA: heatVisits.filter((v) => v.customer_id === 'A'),
  cohort: T.newcomerCohorts(D.firsts, byC(D.cohort), D.asOf),
  cohortOff: T.newcomerCohorts(D.firsts, byC(D.cohort), D.asOf, D.off),
  heat: T.weekHeat(heatVisits, W.addDays(D.asOf, -182), D.asOf),
  heatOff: T.weekHeat(heatVisits, W.addDays(D.asOf, -182), D.asOf, D.off),
  bands: D.times.map(T.bandOf),
  dows: ['2026-10-12', '2026-10-11', '2026-10-10'].map(T.dowMon),
  svc: T.serviceTable(D.svc, svcBy, new Set(D.real), W.addDays(D.asOf, -365), D.asOf),
  svcOff: T.serviceTable(D.svc, svcBy, new Set(D.real), W.addDays(D.asOf, -365), D.asOf, D.off),
  active: T.activeTrend(svcBy, new Set(D.real), D.asOf),
});
"""
TIMES = ["09:59", "12:00", "13:59", "14:00", "17:59", "18:00", "23:10", None, "abc", "9:05"]


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/trends.ts"], SCRIPT, {
        "asOf": AS_OF, "cohort": COHORT_TX, "firsts": FIRSTS, "heat": HEAT_TX,
        "svc": SVC_TX, "real": REAL, "times": TIMES, "off": OFF,
    })
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_visits_one_per_day_earliest_time(ts):
    assert ts["visitsA"] == [{"customer_id": "A", "date": "2026-10-05", "time": "10:00"}]


def test_newcomer_cohorts(ts):
    c = {x["month"]: x for x in ts["cohort"]["cohorts"]}
    assert list(c) == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    # 6월: 3명 중 1명(103일 만에 온 분은 90일을 넘겨 빠진다). 90일이 다 지나 닫힌 달
    assert c["2026-06"] == {"month": "2026-06", "label": "6월", "total": 3, "back": 1, "open": False}
    # 9월: 아직 90일이 안 지났다 — 진행 중
    assert c["2026-09"] == {"month": "2026-09", "label": "9월", "total": 1, "back": 1, "open": True}
    assert c["2026-07"]["open"] is True and c["2026-06"]["open"] is False
    assert sum(x["total"] for x in c.values()) == 4          # 3월·이번 달·날짜 없음은 빠진다
    assert ts["cohort"]["medianDays"] == 35                  # 21·35일 → 통계 화면과 같은 중앙값 규칙


def test_newcomer_cohorts_stretch_for_vacation(ts):
    """90일 사이에 14일 휴가가 끼면 104일까지 본다 — 103일 만에 오신 분(n2)도 다시 오신 분."""
    c = {x["month"]: x for x in ts["cohortOff"]["cohorts"]}
    assert c["2026-06"]["back"] == 2
    # 6월 말 + 90일 + 휴가 14일 = 10.12 > 수집일(10.11) → 아직 진행 중
    assert c["2026-06"]["open"] is True
    assert c["2026-05"]["open"] is False


def test_week_heat(ts):
    h = ts["heat"]
    grid = h["grid"]
    assert grid[0][0] == 1          # 월 오전(같은 날 두 건 → 한 번, 이른 시각)
    assert grid[0][2] == 1          # 수 오전(9:05)
    assert grid[2][5] == 2          # 토 14–16시
    assert grid[4][5] == 1          # 토 18시~
    assert h["total"] == 5 and h["noTime"] == 1
    assert sum(map(sum, grid)) == 5  # 기간 밖·수집일 뒤·충전·연결 없는 거래는 없다
    # 4.12(일)~10.11(일) 183일 — 휴무가 없으면 요일마다 26일, 일요일만 27일. 칸 값은 하루 평균
    assert h["days"] == [26, 26, 26, 26, 26, 26, 27]
    assert h["avg"][2][5] == pytest.approx(2 / 26) and h["max"] == pytest.approx(2 / 26)
    assert h["off"] == [False] * 7


def test_week_heat_with_off_days(ts):
    """화요일 정기 휴무 · 휴가는 영업한 날에서 빠진다. 휴무로 정한 날이라도 방문이 있었으면 영업한 날."""
    h = ts["heatOff"]
    # 화요일: 26일 모두 휴무지만 10.6(E, 시각 없음)에 방문이 있었다 → 그날 하루만 영업한 날
    assert h["days"][1] == 1 and h["off"][1] is False
    # 토요일: 26일 중 휴가 2일(7.4·7.11)과 10.3 → 23일. 평균의 분모가 줄어 같은 2회도 더 붐빈다
    assert h["days"][5] == 23
    assert h["avg"][2][5] == pytest.approx(2 / 23)
    # 목요일: 휴가 7.2·7.9 두 번 → 24일
    assert h["days"][3] == 24


def test_band_and_weekday(ts):
    assert ts["bands"] == [0, 1, 1, 2, 3, 4, 4, None, None, 0]
    assert ts["dows"] == [0, 6, 5]   # 월 0 · 일 6 · 토 5


def test_service_table(ts):
    rows = {r["service"]: r for r in ts["svc"]}
    assert [r["service"] for r in ts["svc"]] == ["여자컷", "남자컷", "뿌리염색"]   # 건수 순, 충전은 없다
    assert rows["여자컷"] == {"service": "여자컷", "count": 3, "avg": 31000, "back": 1, "base": 2}
    assert rows["남자컷"]["base"] == 0          # 워크인 집계는 '다시 옴'을 세지 않는다
    assert rows["뿌리염색"] == {"service": "뿌리염색", "count": 1, "avg": 60000, "back": 0, "base": 1}
    # 휴가(7.1~14)가 끼어도 이 사례들은 기간 안 — 결과는 같다
    assert ts["svcOff"] == ts["svc"]


def test_active_trend(ts):
    """그날까지 90일 안에 방문한 실고객 — 달 말일마다, 마지막은 수집일. 워크인 집계는 빠진다."""
    assert [p["label"] for p in ts["active"]] == ["5월", "6월", "7월", "8월", "9월", "10.11"]
    assert [p["count"] for p in ts["active"]] == [1, 2, 2, 0, 1, 1]
