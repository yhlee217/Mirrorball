"""다음 시술 추천 — web/lib/recommend.ts.

(가) 때가 된 시술: 본인 간격 > 표준표, 휴가 제외, 주기의 1~3배만. (나) 함께 권할 것: 이 매장 기록에서
'종류 A 손님 중 갈래 F 도 받은 비율'(20명 이상 · 15% 이상). 이번 예약 시술의 갈래는 뺀다.
TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

NO_OFF = {"off_weekdays": [], "off_dates": []}
VAC = {"off_weekdays": [], "off_dates": [{"from": "2026-10-01", "to": "2026-10-10"}]}


def tx(cid, date, service, kind="service"):
    return {"customer_id": cid, "date": date, "service": service, "kind": kind}


# A — 뿌리염색 35일마다(본인 간격), 클리닉 한 번(표준 28일), 펌 한 번은 너무 오래돼 '그만두신 쪽'
A = [tx("A", "2026-07-01", "뿌리염색"), tx("A", "2026-08-05", "뿌리염색"), tx("A", "2026-08-05", "클리닉"),
     tx("A", "2026-09-09", "뿌리염색"), tx("A", "2026-01-10", "디지털펌")]

# 매장 — 남자커트 손님 30명 중 12명이 다운펌, 3명이 클리닉도
POP = []
for i in range(30):
    POP.append(tx(f"m{i}", "2026-06-01", "남자컷(원장)"))
    if i < 12:
        POP.append(tx(f"m{i}", "2026-06-20", "남자 다운펌"))
    if 12 <= i < 15:
        POP.append(tx(f"m{i}", "2026-07-01", "두피 클리닉"))
# X — 3주마다 남자커트, 펌은 안 함
X = [tx("X", "2026-09-01", "남자컷"), tx("X", "2026-09-22", "남자컷")]
# Z — 35일마다 뿌리염색(적중률)
Z = [tx("Z", d, "뿌리염색") for d in ("2026-01-01", "2026-02-05", "2026-03-12", "2026-04-16", "2026-05-21")]

SCRIPT = """
const R = require('./recommend.js');
const byA = R.visitsByCustomer(D.A);
const pop = R.visitsByCustomer(D.POP.concat(D.X));
const pairs = R.pairStats(pop, '2026-10-20');
const small = R.pairStats(R.visitsByCustomer(D.POP.filter((t) => Number(t.customer_id.slice(1)) < 19)), '2026-10-20');
const X = pop.get('X');
const byZ = R.visitsByCustomer(D.Z);
out({
  cats: ['남자컷+다운펌', '여자컷(원장)', '선불충전', '뿌리염색 · 클리닉', null].map((s) => R.catsOf(s).sort()),
  visits: R.visitsByCustomer([
    { customer_id: 'q', date: '2026-09-01', service: '여자컷', kind: 'service' },
    { customer_id: 'q', date: '2026-09-01', service: '클리닉', kind: 'service' },
    { customer_id: 'q', date: '2026-09-01', service: '선불충전', kind: 'charge' },
    { customer_id: 'q', date: '2026-09-02', service: '드라이', kind: 'service' },
  ]).get('q'),
  dueA: R.dueServices(byA.get('A'), '2026-10-20', D.NO_OFF),
  dueAvac: R.dueServices(byA.get('A'), '2026-10-20', D.VAC),
  pairMen: pairs['남자커트'],
  crossX: R.crossSell(['남자커트'], pairs),
  crossHasPerm: R.crossSell(['남자커트', '다운펌'], pairs),
  crossSmall: R.crossSell(['남자커트'], small),
  recX: R.recommend(X, pairs, '2026-10-20', D.NO_OFF),
  recXcut: R.recommend(X, pairs, '2026-10-20', D.NO_OFF, ['남자커트']),
  recXperm: R.recommend(X, pairs, '2026-10-20', D.NO_OFF, ['다운펌']),
  bt: R.backtest(byZ, {}, new Set(['Z']), '2026-01-01', '2026-10-11', D.NO_OFF),
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/recommend.ts"], SCRIPT, {"A": A, "POP": POP, "X": X, "Z": Z, "NO_OFF": NO_OFF, "VAC": VAC})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_cats_split_combined_menus(ts):
    assert ts["cats"] == [["남자커트", "다운펌"], ["여자커트"], [], ["뿌리염색", "클리닉"], []]


def test_visits_merge_same_day_and_skip_unknown(ts):
    # 같은 날 두 시술은 한 방문, 충전·종류를 모르는 메뉴(드라이)는 빠진다
    assert ts["visits"] == [{"date": "2026-09-01", "cats": ["여자커트", "클리닉"]}]


def test_due_services(ts):
    d = ts["dueA"]
    # 늘 받던 뿌리염색(본인 35일, 41일 지남)이 먼저, 한 번 받은 클리닉(표준 28일, 76일)이 다음.
    # 펌은 283일 — 표준 90일의 3배를 넘겨 '그만두신 쪽'이라 빠진다
    assert [x["cat"] for x in d] == ["뿌리염색", "클리닉"]
    assert d[0]["personal"] is True and d[0]["cycle"] == 35
    assert d[1]["personal"] is False and d[1]["cycle"] == 28


def test_due_services_skip_vacation(ts):
    # 10.1~10.10 휴가 → 뿌리염색은 41−10=31일, 35일에 못 미쳐 아직 아니다
    assert [x["cat"] for x in ts["dueAvac"]] == ["클리닉"]


def test_pair_stats_from_store_data(ts):
    p = ts["pairMen"]
    assert p["n"] == 31                                   # 매장 30명 + X
    assert p["fam"]["펌"] == {"share": pytest.approx(12 / 31), "label": "다운펌"}
    assert p["fam"]["클리닉"]["share"] == pytest.approx(3 / 31)


def test_cross_sell_rules(ts):
    assert ts["crossX"] == {"fam": "펌", "label": "다운펌", "from": "남자커트", "share": pytest.approx(12 / 31)}
    assert ts["crossHasPerm"] is None     # 이미 펌을 받는 분 — 클리닉은 10%라 근거가 약하다
    assert ts["crossSmall"] is None       # 남자커트 손님이 20명이 안 되면 비율을 믿지 않는다


def test_recommend_composition_and_exclusion(ts):
    r = ts["recX"]
    assert [x["kind"] for x in r] == ["due", "cross"]
    assert r[0]["label"] == "남자커트" and r[0]["reason"] == "마지막 4주 전 · 이 손님은 보통 3주마다"
    assert r[1]["label"] == "다운펌" and r[1]["reason"] == "이 매장 남자커트 손님의 39%가 펌도 받아요 · 주로 다운펌"
    # 이번에 커트를 예약했으면 커트는 빼고, 펌을 예약했으면 펌 갈래는 빼고 권한다
    assert [x["label"] for x in ts["recXcut"]] == ["다운펌"]
    assert [x["label"] for x in ts["recXperm"]] == ["남자커트"]


def test_backtest_hit_rate(ts):
    """35일마다 뿌리염색 — 두 번째 방문부터 매번 '뿌리염색 때'로 맞힌다. 찍어도 늘 뿌리염색이라 base 도 1."""
    bt = ts["bt"]
    assert bt["due"] == {"n": 4, "hit": 4, "base": pytest.approx(1.0)}
    assert bt["cross"]["n"] == 0
