"""작은 화면 결정 — 다시 바뀌지 않게.

2026-10-15 "로그아웃 중앙정렬 · 앱 하단 아이콘 흑백으로": 탭 아이콘은 색 이모지 대신 글자색을 따르는 선 아이콘
(고른 탭은 검게), 로그아웃은 가운데에 손가락 크기로.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def test_tab_icons_are_monochrome_lines():
    tab = (WEB / "app" / "tab-bar.tsx").read_text(encoding="utf-8")
    assert "<TabIcon name={t.icon} />" in tab
    icons_used = re.findall(r"icon: '([^']*)'", tab)
    assert icons_used == ["home", "customers", "care", "visits"], icons_used   # 이모지가 아니라 선 아이콘 이름
    icons = (WEB / "components" / "tab-icons.tsx").read_text(encoding="utf-8")
    assert 'stroke="currentColor"' in icons and 'fill="none"' in icons
    for name in ("home", "customers", "care", "visits"):
        assert f"  {name}: (" in icons, name
    css = (WEB / "app" / "globals.css").read_text(encoding="utf-8")
    assert ".tab.on{color:var(--ink)}" in css                                 # 고른 탭은 검게(흑백)
    audit = (WEB / "scripts" / "ui-audit" / "render.cjs").read_text(encoding="utf-8")
    assert "r(TabIcon, { name: i })" in audit                                 # 측정 견본도 같은 아이콘


def test_logout_is_centered_with_a_finger_sized_target():
    settings = (WEB / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
    assert '<div className="logout-row"><LogoutButton /></div>' in settings
    css = (WEB / "app" / "globals.css").read_text(encoding="utf-8")
    assert ".logout-row{text-align:center}" in css and ".logout-row .linkbtn{padding:13px 28px" in css
