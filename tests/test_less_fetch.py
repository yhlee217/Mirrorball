"""덜 받기(개선 계획 v12 P0) — 받는 거래를 줄여도 화면 숫자는 그대로.

통계는 매장 거래 전부 → 최근 2년(+31일), 홈은 매장 1년 거래 → 지난 두 주 · 예약 손님의 1년 이력 · 첫 방문 손님의 그날 거래 ·
저장해 둔 추천 근거. 5년치 견본 매장(지어낸 손님 · 거래)으로 '전부 받았을 때'와 '줄여 받았을 때'의 계산 결과를 견준다 —
하나라도 다르면 덜 받기가 숫자를 바꾼 것이다. 2년보다 오래된 이력이 답을 바꾸는 계산(연락 효과의 첫 방문 손님/단골 가르기,
첫 방문 안부 효과)은 손님 표의 첫 방문 · 연락한 분의 전체 이력으로 메운다(lib/trends withOlderHistory).
"""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

TODAY = "2026-10-15"
AS_OF = "2026-10-11"
SERVICES = ["여자컷", "남자컷", "뿌리염색", "전체염색", "디지털펌", "셋팅펌", "클리닉", "두피스파", "매직"]


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _store(seed: int = 7) -> dict:
    """지어낸 5년치 매장 — 단골 · 한 번 오신 분 · 오래 쉬다 다시 오신 분 · 최근 연락한 분이 섞인다."""
    rnd = random.Random(seed)
    as_of = _d(AS_OF)
    customers, tx, contacts = [], [], []
    for i in range(320):
        cid = f"c{i:03d}"
        start = _d("2019-01-01") + dt.timedelta(days=rnd.randrange(0, (as_of - _d("2019-01-01")).days))
        cycle = rnd.choice([21, 28, 35, 42, 56, 70, 90])
        dates, day = [], start
        while day <= as_of:
            dates.append(day)
            if rnd.random() < (0.35 if len(dates) == 1 else 0.06):    # 한 번 오고 안 오시는 분이 많다
                break
            day = day + dt.timedelta(days=max(7, int(rnd.gauss(cycle, cycle * 0.25))))
        if i % 23 == 0 and dates[0] < _d("2023-06-01"):              # 오래 쉬다 이번 달에 다시 오신 분
            dates.append(_d("2026-10-02") + dt.timedelta(days=i % 5))
        for d in dates:
            n = 1 if rnd.random() < 0.7 else 2
            for svc in rnd.sample(SERVICES, n):
                tx.append({"customer_id": cid, "date": d.isoformat(), "time": f"{rnd.randrange(10, 20):02d}:{rnd.choice(['00', '30'])}",
                           "service": svc, "amount_won": rnd.randrange(3, 30) * 10000, "kind": None, "covered_won": 0})
            if rnd.random() < 0.05:
                tx.append({"customer_id": cid, "date": d.isoformat(), "time": None, "service": "선불충전",
                           "amount_won": 300000, "kind": "charge", "covered_won": 0})
        customers.append({"id": cid, "first_visit": dates[0].isoformat(), "last_visit": dates[-1].isoformat(),
                          "visit_count": len(dates)})
        if rnd.random() < 0.12:                                        # 최근 3주 연락
            sent = dt.datetime(2026, 9, 26, 3, 0) + dt.timedelta(hours=rnd.randrange(0, 24 * 18))
            contacts.append({"customer_id": cid, "sent_at": sent.isoformat() + "Z"})
    return {"customers": customers, "tx": tx, "contacts": contacts}


def test_stats_numbers_unchanged_with_two_years():
    got = run_ts(["lib/trends.ts", "lib/effect.ts", "lib/forecast.ts", "lib/recommend.ts", "lib/settings.ts", "lib/week.ts"], """
const T = require('./trends.js');
const E = require('./effect.js');
const { monthForecast } = require('./forecast.js');
const { backtest, pairStats, visitsByCustomer } = require('./recommend.js');
const { mergeSettings } = require('./settings.js');
const { addDays } = require('./week.js');
const s = mergeSettings({});
const realIds = new Set(D.customers.map((c) => c.id));
const since = addDays(D.today, -T.STATS_DAYS);
const asJson = (m) => JSON.stringify(m instanceof Map ? [...m.entries()].sort() : m);
const run = (tx, realVisits) => {
  const visits = T.toVisits(tx);
  const byCust = T.datesByCustomer(visits);
  const rec = visitsByCustomer(tx.filter((t) => t.date >= addDays(D.asOf, -730)));
  return {
    cohort: asJson(T.newcomerCohorts(D.customers, byCust, D.asOf, s)),
    heat: asJson(T.weekHeat(visits, addDays(D.asOf, -182), D.asOf, s)),
    svc: asJson(T.serviceTable(tx, byCust, realIds, addDays(D.asOf, -364), D.asOf, s)),
    active: asJson(T.activeTrend(byCust, realIds, D.asOf)),
    forecast: asJson(monthForecast(tx, '2026-10', D.asOf, s, new Set(visits.map((v) => v.date)))),
    hits: asJson(backtest(rec, pairStats(rec, D.asOf), realIds, addDays(D.asOf, -364), D.asOf, s)),
    groups: asJson(E.contactEffectByGroup(D.contacts, realVisits(byCust), new Set())),
    hello: asJson(E.helloEffect(D.contacts, realVisits(byCust))),
    effect: asJson(E.contactEffect(D.contacts, realVisits(byCust), new Set(), '2026-09-18')),
  };
};
const full = run(D.tx, (byCust) => byCust);
const recent = D.tx.filter((t) => t.date >= since);
const contactedIds = new Set(D.contacts.map((c) => c.customer_id));
const contactedFull = T.datesByCustomer(T.toVisits(D.tx.filter((t) => contactedIds.has(t.customer_id))));
const less = run(recent, (byCust) => T.withOlderHistory(byCust, D.customers, contactedFull, since));
out({ full, less, dropped: D.tx.length - recent.length, total: D.tx.length,
      oldFirst: D.customers.filter((c) => c.first_visit < since).length });
""", {**_store(), "today": TODAY, "asOf": AS_OF})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["dropped"] > got["total"] * 0.3 and got["oldFirst"] > 50     # 견본이 2년 넘는 이력을 충분히 품었다
    for key, value in got["full"].items():
        assert got["less"][key] == value, key


def test_home_numbers_unchanged_with_narrow_fetches():
    got = run_ts(["lib/week.ts", "lib/customers.ts", "lib/recommend.ts", "lib/trends.ts"], """
const W = require('./week.js');
const { servicesOn } = require('./customers.js');
const { pairStats, visitsByCustomer } = require('./recommend.js');
const { toVisits } = require('./trends.js');
const byId = new Map(D.customers.map((c) => [c.id, c]));
const wk = W.lastWeek(D.asOf, D.today);
const yearFrom = W.addDays(D.asOf, -365);
const inRange = (t, a, b) => t.date >= a && t.date <= b;
const yearTx = D.tx.filter((t) => inRange(t, yearFrom, D.asOf));                       // 전: 매장 1년 전부
// 후: app/page.tsx 가 받는 넷
const weekTx = D.tx.filter((t) => inRange(t, wk.prev.start, wk.cur.end));
const booked = D.customers.filter((_, i) => i % 9 === 0).map((c) => c.id);
const bookedSet = new Set(booked);
const bookedTx = D.tx.filter((t) => bookedSet.has(t.customer_id) && inRange(t, yearFrom, D.asOf));
const onesIds = new Set(D.customers.filter((c) => c.visit_count === 1 && c.last_visit >= yearFrom).map((c) => c.id));
const onesTx = D.tx.filter((t) => onesIds.has(t.customer_id) && inRange(t, yearFrom, D.asOf));
const storeTx = D.tx.filter((t) => t.date >= W.addDays(D.today, -365));                // lib/store-stats 가 하루 한 번
const firsts = D.customers.map((c) => c.first_visit);
const dayOf = (id) => (byId.get(id)?.visit_count === 1 ? byId.get(id)?.last_visit : null);
const pick = (m, ids) => JSON.stringify(ids.map((id) => m.get(id) ?? null));
const days = (tx) => [...new Set(toVisits(tx).map((v) => v.date))].filter((d) => d >= wk.prev.start && d <= wk.cur.end).sort();
out({
  week: [JSON.stringify([W.weekNums(yearTx, firsts, wk.cur), W.weekNums(yearTx, firsts, wk.prev)]),
         JSON.stringify([W.weekNums(weekTx, firsts, wk.cur), W.weekNums(weekTx, firsts, wk.prev)])],
  workDays: [JSON.stringify(days(yearTx)), JSON.stringify(days(weekTx))],
  ones: [JSON.stringify([...servicesOn(yearTx, dayOf).entries()].sort()), JSON.stringify([...servicesOn(onesTx, dayOf).entries()].sort())],
  booked: [pick(visitsByCustomer(yearTx), booked), pick(visitsByCustomer(bookedTx), booked)],
  pairs: [JSON.stringify(pairStats(visitsByCustomer(yearTx), D.today)), JSON.stringify(pairStats(visitsByCustomer(storeTx), D.today))],
  sizes: { year: yearTx.length, week: weekTx.length, booked: bookedTx.length, ones: onesTx.length },
});
""", {**_store(), "today": TODAY, "asOf": AS_OF})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    for key in ("week", "workDays", "ones", "booked", "pairs"):
        before, after = got[key]
        assert before == after, key
    z = got["sizes"]
    assert z["week"] + z["booked"] + z["ones"] < z["year"] / 2                # 홈이 받는 줄이 절반 아래로


def test_pages_fetch_what_the_tests_assume():
    """위 두 테스트가 흉내 낸 받기를 화면이 실제로 한다 — 기간 · 손님 조건이 바뀌면 여기서 걸린다."""
    home = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    assert ".gte('date', wk.prev.start).lte('date', wk.cur.end)" in home
    assert "txsOfCustomers<WeekTx>(supabase, tenantId, ids, 'customer_id,date,kind,service,amount_won,covered_won', yearFrom, asOf)" in home
    assert "c.visit_count === 1 && (c.last_visit ?? '').slice(0, 10) >= yearFrom" in home
    assert "storePairs(supabase, tenantId, today)" in home and "yearTx" not in home
    carte = (WEB / "app" / "customer" / "[id]" / "data.ts").read_text(encoding="utf-8")
    assert "storePairs(supabase, cust.tenant_id, today)" in carte and "pairStats(" not in carte
    pairs = (WEB / "lib" / "store-stats.ts").read_text(encoding="utf-8")
    assert ".gte('date', addDays(today, -365))" in pairs and "row.as_of === today" in pairs
    stats = (WEB / "app" / "stats" / "page.tsx").read_text(encoding="utf-8")
    assert ".gte('date', txSince)" in stats and "addDays(kToday, -STATS_DAYS)" in stats
    assert "{ count: 'exact', head: true }" in stats and "tx={txTotal ?? tx.length}" in stats
    assert "withOlderHistory(" in stats
    alerts = (WEB / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    assert "const [firstTx, lastTx, effTx] = await Promise.all([" in alerts   # 차례로 세 번 → 한꺼번에
    assert alerts.count("await txsOf(") == 0
