"""'이번 주 새로'(web/lib/fresh.ts, 개선 계획 v10 P1) — 챙길 고객에 이번 수집으로 새로 오른 분.

2026-10-15 첫 사용 숫자: 연락 기록이 생긴 10.12 뒤 세 매장 모두 연락 0명. 한 매장 84명을 50명씩 펼치는 목록에
'이번 주엔 누구부터'가 없었다. 지난주 수집(asOf − 7일) 땐 목록에 없던 분을 맨 위에 모은다 — 경계가 하루라도
어긋나면 지난주에 이미 있던 분이 '새로'로 뜨거나, 정말 새로 오른 분이 묻힌다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent

ASOF = "2026-10-11"   # 이번 수집(일)
TODAY = "2026-10-15"  # 목요일 — 지난주 수집은 10.04


def _run(cases: list[dict], extra: dict | None = None):
    return run_ts(["lib/fresh.ts", "lib/settings.ts"], """
const { newOnList, lastContactDays } = require('./fresh.js');
const { mergeSettings } = require('./settings.js');
const { quietIds } = require('./contact.js');
out({
  fresh: D.cases.map((k) => newOnList(k.state, { last_visit: k.last ?? null, revisit_cycle_days: k.cyc ?? null }, {
    settings: mergeSettings(k.off ? { off_dates: k.off } : {}), asOf: D.asOf, today: D.today,
    services: k.svcs ?? [], lastContact: k.contact ?? null,
  })),
  last: Object.fromEntries([...lastContactDays(D.rows).entries()]),
  quiet: [...quietIds(D.rows, Date.parse(D.now))].sort(),
});
""", {"cases": cases, "asOf": ASOF, "today": TODAY, **(extra or {"rows": [], "now": "2026-10-15T03:00:00Z"})})


CASES = [
    # 재방문 도래 · 이탈 위험 — 지난주 수집(10.04) 때 평소 주기가 아직 안 됐으면 새로
    ({"state": "due", "last": "2026-08-31", "cyc": 35}, True),       # 10.04 엔 34일 — 주기 전
    ({"state": "due", "last": "2026-08-30", "cyc": 35}, False),      # 10.04 엔 35일 — 이미 재방문 도래
    ({"state": "overdue", "last": "2026-06-01", "cyc": 35}, False),  # 오래전부터 목록에
    ({"state": "due", "last": "2026-08-24", "cyc": None}, True),     # 주기 모름 → 42일, 10.04 엔 41일
    ({"state": "due", "last": "2026-08-23", "cyc": None}, False),    # 10.04 엔 42일
    # 휴가 — 그 사이 쉰 날은 '안 오신 날'이 아니다(지금 판정 careState 와 같은 셈)
    ({"state": "due", "last": "2026-08-30", "cyc": 35, "off": [{"from": "2026-09-10", "to": "2026-09-12"}]}, True),
    # 첫 방문 안부 — 지난주 수집 뒤의 첫 방문만
    ({"state": "hello", "last": "2026-10-05"}, True),
    ({"state": "hello", "last": "2026-10-04"}, False),
    # 다시 오실 때 — 그때는 주기(모르면 42일) 전이었나. 그때 안부(첫 방문 14일 안)였으면 이미 목록에 있었다
    ({"state": "back", "last": "2026-08-24"}, True),
    ({"state": "back", "last": "2026-08-23"}, False),
    ({"state": "back", "last": "2026-09-24"}, False),
    # 연락 뒤 숨김(14일)이 지난 7일 안에 끝나 다시 오른 분 — 상태로는 오래전부터 목록이어도
    ({"state": "overdue", "last": "2026-06-01", "cyc": 35, "contact": "2026-10-01"}, True),   # 오늘 끝남
    ({"state": "overdue", "last": "2026-06-01", "cyc": 35, "contact": "2026-09-25"}, True),   # 10.09 끝남
    ({"state": "overdue", "last": "2026-06-01", "cyc": 35, "contact": "2026-09-24"}, False),  # 10.08 — 일주일 전
    ({"state": "due", "last": None}, False),
]


def test_new_on_list_boundaries():
    got = _run([c for c, _ in CASES])
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    for (case, want), have in zip(CASES, got["fresh"]):
        assert have is want, case


def test_last_contact_and_quiet_from_one_log():
    """홈은 연락 기록 하나(21일)로 숨김(14일)과 마지막 연락일(KST)을 함께 센다 — 따로 받던 숨김과 같은 셈."""
    rows = [
        {"customer_id": "a", "sent_at": "2026-09-24T02:00:00Z"},
        {"customer_id": "a", "sent_at": "2026-10-01T16:00:00Z"},   # KST 10.02 01:00 — 가장 늦은 연락
        {"customer_id": "b", "sent_at": "2026-09-30T02:00:00Z"},   # 15일 전 — 숨김 끝
        {"customer_id": "c", "sent_at": "2026-10-14T09:00:00Z"},
        {"customer_id": None, "sent_at": "2026-10-14T09:00:00Z"},
        {"customer_id": "d", "sent_at": None},
    ]
    got = _run([], {"rows": rows, "now": "2026-10-15T03:00:00Z"})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["last"] == {"a": "2026-10-02", "b": "2026-09-30", "c": "2026-10-14"}
    assert got["quiet"] == ["a", "c"]


def test_home_and_care_list_use_the_same_rule():
    """홈 알약 '새로 N'과 챙길 고객 맨 위는 같은 판정 · 같은 연락 기록 · 같은 기준일."""
    home = (ROOT / "web" / "app" / "page.tsx").read_text(encoding="utf-8")
    alerts = (ROOT / "web" / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    for src in (home, alerts):
        assert "newOnList(" in src and "lastContactDays(" in src
    assert "recentContactRows(supabase, tenantId, CONTACT_QUIET_DAYS + NEW_DAYS)" in home
    assert "Number(b.fresh) - Number(a.fresh)" in alerts   # 새로 오른 분을 맨 위에
