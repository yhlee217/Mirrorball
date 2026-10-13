"""목록 상태를 주소에 담기 — web/lib/list-state.ts(모바일 개선 M2).

카르테를 보고 돌아와도 검색·조건·펼친 수가 그대로여야 한다. 주소는 사람이 고치거나 옛 링크로도 들어오므로
모르는 값은 버리고, 기본값은 주소에 적지 않는다. TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

SCRIPT = """
const L = require('./list-state.js');
const dec = (q) => { const p = new URLSearchParams(q); return L.decodeList((k) => p.get(k)); };
const full = { q: '김서', chips: ['vip', 'overdue'], more: false, visit: 'reg', rev: '', rec: '3m', svc: '', sort: 'revenue' };
out({
  empty: dec(''),
  legacy: dec('filter=nogender'),
  junk: dec('f=overdue,hack&v=zzz&o=drop&q=' + 'x'.repeat(60)),
  enc: L.encodeList(full),
  round: dec(L.encodeList(full)),
  dflt: L.encodeList(L.LIST_DEFAULT),
  alerts: ['', 'n=100&open=3f2b1c9a-1234-4cde-8f00-0123456789ab', 'n=73', 'n=999999', 'open=<script>'].map((q) => {
    const p = new URLSearchParams(q); return L.decodeAlerts((k) => p.get(k), 50);
  }),
  alertsEnc: [L.encodeAlerts(50, null, 50), L.encodeAlerts(100, 'abc12345', 50)],
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/list-state.ts"], SCRIPT, {})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_empty_url_is_default(ts):
    assert ts["empty"] == {"q": "", "chips": [], "more": False, "visit": "", "rev": "", "rec": "", "svc": "", "sort": "recent"}
    assert ts["dflt"] == ""                                  # 아무것도 안 걸면 주소도 깨끗하게


def test_legacy_filter_link_opens_folded_panel(ts):
    # 통계 '성별 미상' 링크(?filter=nogender) — 접힌 조건이라 '필터'를 펼친 채로
    assert ts["legacy"]["chips"] == ["nogender"] and ts["legacy"]["more"] is True


def test_unknown_values_are_dropped(ts):
    j = ts["junk"]
    assert j["chips"] == ["overdue"] and j["visit"] == "" and j["sort"] == "recent" and len(j["q"]) == 40


def test_round_trip(ts):
    assert ts["enc"] == "q=%EA%B9%80%EC%84%9C&f=overdue%2Cvip&v=reg&rc=3m&o=revenue"   # 기본값(정렬·접힘)은 안 적는다
    r = ts["round"]
    assert r["q"] == "김서" and sorted(r["chips"]) == ["overdue", "vip"] and r["more"] is True   # 고른 셀렉트가 있으면 펼침
    assert (r["visit"], r["rec"], r["sort"]) == ("reg", "3m", "revenue")


def test_alerts_shown_and_open(ts):
    a = ts["alerts"]
    assert a[0] == {"shown": 50, "open": None}
    assert a[1] == {"shown": 100, "open": "3f2b1c9a-1234-4cde-8f00-0123456789ab"}
    assert a[2]["shown"] == 100                              # 50명씩 — 73 이면 100까지 펼친다
    assert a[3]["shown"] == 2000                             # 터무니없는 값은 막는다
    assert a[4]["open"] is None                              # id 모양이 아니면 버린다
    assert ts["alertsEnc"] == ["", "n=100&open=abc12345"]
