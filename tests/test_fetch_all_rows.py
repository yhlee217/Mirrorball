"""1,000행씩 나눠 받기 — web/lib/customers.ts fetchAllRows.

PostgREST 는 한 번에 1,000행까지만 준다. 다 받되(빠뜨리거나 겹치면 매출·방문이 틀린다),
첫 쪽이 꽉 차면 다음 쪽들은 넷씩 한꺼번에 받는다(개선 계획 v4 0-3). 가짜 조회로 순서·호출 수·
동시에 몇 개가 떠 있는지·오류 전달을 본다. TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

SCRIPT = """
const { fetchAllRows } = require('./customers.js');
// total 행이 있는 표 — range(from, to) 대로 잘라 준다. 호출과 동시 실행 수를 센다.
const table = (total, failAt = -1) => {
  const log = { calls: [], live: 0, peak: 0 };
  const q = async (from, to) => {
    log.calls.push(from);
    log.live++; log.peak = Math.max(log.peak, log.live);
    await new Promise((r) => setTimeout(r, 1));
    log.live--;
    if (from === failAt) return { data: null, error: { message: 'boom' } };
    const n = Math.max(0, Math.min(to, total - 1) - from + 1);
    return { data: Array.from({ length: n }, (_, i) => from + i), error: null };
  };
  return { q, log };
};
(async () => {
  const res = {};
  for (const total of D.totals) {
    const { q, log } = table(total);
    const rows = await fetchAllRows(q);
    res[total] = {
      n: rows.length,
      inOrder: rows.every((v, i) => v === i),
      calls: log.calls.length,
      peak: log.peak,
    };
  }
  const { q } = table(9300, 3000);
  try { await fetchAllRows(q); res.error = null; } catch (e) { res.error = e.message; }
  out(res);
})();
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/customers.ts"], SCRIPT, {"totals": [0, 999, 1000, 4000, 9300]})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_gets_every_row_in_order(ts):
    for total in ("0", "999", "1000", "4000", "9300"):
        assert ts[total]["n"] == int(total), total
        assert ts[total]["inOrder"], total


def test_small_tables_take_one_call(ts):
    assert ts["0"]["calls"] == 1 and ts["999"]["calls"] == 1


def test_later_pages_go_four_at_a_time(ts):
    # 9,300행: 첫 쪽 1번 + 넷씩 세 묶음(1~4, 5~8, 9~12) — 차례로 10번 기다리던 것이 4번
    assert ts["9300"]["calls"] == 13
    assert ts["9300"]["peak"] == 4
    # 꽉 찬 첫 쪽 뒤엔 끝인지 모르니 한 묶음은 더 본다
    assert ts["1000"]["calls"] == 5
    assert ts["4000"]["calls"] == 5          # 1~3 꽉 참 + 4 빈 쪽 → 끝


def test_error_is_not_swallowed(ts):
    assert ts["error"] == "boom"
