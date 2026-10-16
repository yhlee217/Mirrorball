"""운영자 화면(/ops, 개선 계획 v12 P2) — 매일 감시와 같은 숫자 · 같은 모양, 운영자 폰에서만.

전에는 매장별 사용 · 연락 · 화면 속도를 GitHub 감시 기록에서만 볼 수 있었다(제가 읽어 드려야 했다). 숫자뿐인 화면이지만
디자이너께 사용을 재촉하지 않게 디자이너 화면엔 입구가 없고, 운영자 폰(설정 ?op=1 → 쿠키)이 아니면 열리지 않는다.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)

NOW = dt.datetime(2026, 10, 22, 1, 0, tzinfo=dt.timezone.utc)
SINCE = "2026-10-15T06:01:02.123+00:00"
USAGE_0025 = [
    {"slug": "daunbu", "screens_7d": 0, "app_7d": 0, "op_7d": 0, "contacts_7d": 0, "last_seen": None, "since": SINCE},
    {"slug": "hayewoni", "screens_7d": 12, "app_7d": 10, "op_7d": 35, "contacts_7d": 3,
     "last_seen": (NOW - dt.timedelta(hours=2)).isoformat(), "since": SINCE},
    {"slug": "juhwan", "screens_7d": 3, "app_7d": 0, "op_7d": 0, "contacts_7d": 2,
     "last_seen": (NOW - dt.timedelta(days=2, hours=1)).isoformat(), "since": SINCE},
]
USAGE_0024 = [{"slug": "hayewoni", "screens_7d": 47, "contacts_7d": 0, "last_seen": (NOW - dt.timedelta(hours=3)).isoformat()}]
SPEED = [
    {"screen": "/stats", "opened": 12, "p50_ms": 3210, "p90_ms": 5480, "instant": 2},
    {"screen": "/alerts", "opened": 3, "p50_ms": None, "p90_ms": None, "instant": 3},
]


def test_ops_screen_says_what_the_daily_watch_says():
    got = run_ts(["lib/ops-view.ts"], """
const V = require('./ops-view.js');
const now = Date.parse(D.now);
out({
  u25: D.u25.map((r) => r.slug + ' ' + V.usageLine(r, now)),
  u24: D.u24.map((r) => r.slug + ' ' + V.usageLine(r, now)),
  since: V.sinceLine(D.u25), since24: V.sinceLine(D.u24),
  speed: D.speed.map((r) => r.screen + ' ' + V.speedLine(r)),
});
""", {"u25": USAGE_0025, "u24": USAGE_0024, "speed": SPEED, "now": NOW.isoformat()})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    norm = lambda s: " ".join(s.split())
    assert [norm(x) for x in got["u25"]] == [norm(x) for x in shc.fmt_usage(USAGE_0025, NOW)[1:]]
    assert [norm(x) for x in got["u24"]] == [norm(x) for x in shc.fmt_usage(USAGE_0024, NOW)]
    assert got["since"] == "화면 기록 10.15 15:01부터 · 운영자 폰은 따로 셈" and got["since24"] is None
    assert [norm(x) for x in got["speed"]] == [norm(x) for x in shc.fmt_speed(SPEED)]


def test_ops_screen_opens_only_for_the_operator():
    """0027 뒤엔 운영자 계정만(lib/ops-gate — 쿠키는 누구나 켤 수 있다), 그 전엔 운영자 폰 쿠키(v15 P2)."""
    page = (WEB / "app" / "ops" / "page.tsx").read_text(encoding="utf-8")
    body = page[page.index("export default async function OpsPage"):]
    assert "const opCookie = (await cookies()).get('mb-op')?.value === '1';" in body
    gate_line = next(l for l in body.splitlines() if "notFound();" in l)
    assert "canSeeOps(supabase, opCookie)" in gate_line
    gate = body.index(gate_line)
    assert body.index("requireUser()") < gate < body.index("supabase.rpc('ops_usage')")   # 문을 본 뒤에야 숫자를 읽는다
    for banned in ("from('customers')", "from('transactions')", "pii_enc", "contactReader"):
        assert banned not in page, banned                                                  # 손님 정보는 안 읽는다
    settings = (WEB / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
    assert "get('mb-op')?.value === '1' && (await canSeeOps(supabase, true)) ? (" in settings and 'href="/ops"' in settings
    mark = (WEB / "components" / "op-mark.tsx").read_text(encoding="utf-8")
    assert "setOpCookie(q === '1')" in mark
    timer = (WEB / "components" / "screen-timer.tsx").read_text(encoding="utf-8")
    assert "if (isOp() && !document.cookie.includes('mb-op=1')) setOpCookie(true);" in timer   # 쿠키 전에 표시한 폰
