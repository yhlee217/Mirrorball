"""처음 들어오는 길(개선 계획 v11 P0) — 매장 연결 전 계정 · 데모는 뒤로 · 로그인 없이 여는 시작 안내.

전에는 매장 연결 전에 로그인하면 홈이 '데모 데이터로 시작'만 보여 줬고, 누르면 데모가 '가장 먼저 소속된 매장'이 되어
운영자가 실제 매장을 이어도 데모가 열렸다(SQL 로 소속을 지워야 풀림). 시작 안내는 로그인 전 화면이라 손님 정보를
읽는 코드가 들어가면 안 된다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsnode import run_ts

WEB = Path(__file__).resolve().parent.parent / "web"


def test_real_salon_wins_over_demo():
    got = run_ts(["lib/tenant-pick.ts"], """
const { pickTenant, isDemoSlug } = require('./tenant-pick.js');
out({ picks: D.cases.map(pickTenant), demo: ['demo-1a2b3c4d', 'hayewoni', null, 'demo'].map(isDemoSlug) });
""", {"cases": [
        [{"tenant_id": "D", "tenants": {"slug": "demo-1a2b3c4d"}}, {"tenant_id": "R", "tenants": {"slug": "hayewoni"}}],
        [{"tenant_id": "R", "tenants": {"slug": "hayewoni"}}, {"tenant_id": "S", "tenants": {"slug": "juhwan"}}],
        [{"tenant_id": "D", "tenants": [{"slug": "demo-1a2b3c4d"}]}, {"tenant_id": "R", "tenants": [{"slug": "daunbu"}]}],
        [{"tenant_id": "D", "tenants": {"slug": "demo-1a2b3c4d"}}],                       # 데모뿐이면 데모
        [{"tenant_id": "X", "tenants": None}, {"tenant_id": "R", "tenants": {"slug": "hayewoni"}}],  # 이름을 못 읽으면 실제로
        [],
    ]})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["picks"] == ["R", "R", "R", "D", "X", None]
    assert got["demo"] == [True, False, False, False]


def test_current_tenant_uses_pick_and_keeps_a_fallback():
    src = (WEB / "lib" / "tenant.ts").read_text(encoding="utf-8")
    fn = src[src.index("export async function getTenantId"):]
    fn = fn[: fn.index("\n}\n")]
    assert "select('tenant_id,tenants(slug)')" in fn and "pickTenant(" in fn
    assert fn.count(".order('created_at', { ascending: true })") == 2      # 둘 다 가장 먼저 소속된 순서
    assert "if (!error)" in fn and ".limit(1).maybeSingle()" in fn         # 매장 이름을 못 읽어도 매장을 잃지 않는다
    onboard = (WEB / "app" / "api" / "onboard" / "route.ts").read_text(encoding="utf-8")
    assert "DEMO_PREFIX + user.id" in onboard                               # 데모 이름표가 고르는 규칙과 같다


def test_no_salon_screen_shows_email_and_keeps_demo_small():
    home = (WEB / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "<NoSalon email={user.email ?? null} />" in home and "OnboardButton" not in home
    screen = (WEB / "app" / "no-salon.tsx").read_text(encoding="utf-8")
    assert "{email}" in screen and 'href="/"' in screen and '다른 이메일로 로그인' in screen and "<OnboardButton />" in screen
    demo = (WEB / "app" / "onboard-button.tsx").read_text(encoding="utf-8")
    assert 'className="linkbtn"' in demo and "window.confirm(" in demo


def test_start_page_is_public_and_reads_nothing():
    """시작 안내는 로그인 없이 열린다 — 로그인 · 매장 · 손님 정보를 읽는 코드가 없어야 한다."""
    src = (WEB / "app" / "start" / "page.tsx").read_text(encoding="utf-8")
    for banned in ("supabase", "requireUser", "requireTenant", "getTenantId", "lib/tenant", "lib/crypto",
                   "fetch(", "force-dynamic", "cookies", "'use client'"):
        assert banned not in src, banned
    assert 'href="/login"' in src and "홈 화면에 추가" in src
    tab = (WEB / "app" / "tab-bar.tsx").read_text(encoding="utf-8")
    assert "p.startsWith('/start')" in tab                                  # 로그인 전 화면엔 탭이 없다
    settings = (WEB / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
    assert 'href="/start"' in settings
