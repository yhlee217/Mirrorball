"""멈춘 자료 안내(개선 계획 v17 P0, 2026-11-25) — 수집을 쉬는 동안 앱이 틀린 말을 하지 않게.

11.23 수집을 쉬기로 했고 앱 데이터는 10.21 에서 멈췄다. 챙길 고객은 그 뒤 다녀가신 분도 '오실 때 지남'으로 띄워, 목록대로
연락하면 지난달에 오신 손님께 '오실 때 됐어요'가 간다. 8일 넘게 밀리면(앱의 '수집 밀림'과 같은 기준) 홈 · 챙길 고객 ·
오늘 예약에 문장으로 밝힌다. 켜고 끄는 값 없이 마지막 수집 날짜로 판단 — 수집이 다시 돌면 저절로 사라진다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_notes_appear_only_after_eight_days_and_name_the_date():
    got = run_ts(["lib/sync.ts"], """
const { frozenNote } = require('./sync.js');
const wheres = ['home', 'care', 'today', 'row'];
out({
  none: wheres.map((w) => frozenNote(null, w)),
  fresh: wheres.map((w) => frozenNote(D.fresh, w)),
  stale: Object.fromEntries(wheres.map((w) => [w, frozenNote(D.stale, w)])),
});
""", {"fresh": {"date": "2026-10-21", "daysAgo": 7}, "stale": {"date": "2026-10-21", "daysAgo": 8}})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["none"] == [None] * 4 and got["fresh"] == [None] * 4                  # 7일까지는 평소대로 칩만
    st = got["stale"]
    assert st["home"] == "자료는 10.21까지예요 — 그 뒤 예약 · 방문은 아직 안 보여요"
    assert st["care"] == "10.21 뒤에 오셨을 수 있어요 — 연락 전에 HandSOS 에서 마지막 방문을 확인하세요"
    assert st["today"] == "예약은 10.21에 받은 것까지예요 — 오늘 예약은 HandSOS 에서 보세요"
    assert st["row"] == "10.21 뒤 방문은 아직 안 보여요 — 연락 전에 HandSOS 에서 확인"


def test_home_and_care_show_the_notes_in_the_right_places():
    home = (WEB / "app" / "home-view.tsx").read_text(encoding="utf-8")
    top = home.index('className="top"')
    assert top < home.index("<FrozenNote text={frozenNote(synced, 'home')} />") < home.index('<div className="sect-h">')
    assert "hint={frozenNote(synced, 'today') ?? undefined}" in home                    # 오늘 예약이 비었을 때만
    page = (WEB / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    assert page.index("<FrozenNote text={frozenNote(synced, 'care')} />") < page.index("<AlertsList")
    assert "frozen={frozenNote(synced, 'row')}" in page
    lst = (WEB / "app" / "alerts" / "alerts-list.tsx").read_text(encoding="utf-8")
    x = lst.index('<div className="crow-x">')
    assert x < lst.index("<FrozenNote text={frozen} small />") < lst.index('<div className="crow-acts">')   # 펼친 줄, 보내기 위
    css = (WEB / "app" / "globals.css").read_text(encoding="utf-8")
    assert ".frozen{" in css and ".frozen-s{" in css


def test_no_switch_to_forget_it_is_the_last_sync_that_decides():
    src = (WEB / "lib" / "sync.ts").read_text(encoding="utf-8")
    body = src[src.index("export function frozenNote"):]
    assert "if (!s || !isSyncStale(s)) return null;" in body                         # 수집이 다시 돌면 저절로 사라진다
    for banned in ("process.env", "COLLECT_PAUSED", "localStorage"):
        assert banned not in body, banned
