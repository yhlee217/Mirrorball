"""운영 안내서(playbook/OPERATIONS_APP.md, 개선 계획 v13 P2) — 적힌 명령 · 경로 · SQL 파일이 실제와 같다.

안내서가 낡으면 운영자가 없는 스크립트를 돌리거나 SQL 하나를 빠뜨린다. 파일 이름이 바뀌면 여기서 걸린다.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "playbook" / "OPERATIONS_APP.md").read_text(encoding="utf-8")


def test_scripts_and_paths_exist():
    for rel in sorted(set(re.findall(r"(worker/[a-z_]+\.(?:py|sh))", DOC))):
        assert (ROOT / rel).exists(), rel
    for rel in ("playbook/KEY_ROTATION.md", "DEPLOY.md", "LAUNCH.md", "playbook/OPERATIONS.md"):
        assert rel in DOC and (ROOT / rel).exists(), rel


def test_every_migration_is_listed():
    files = sorted(p.name for p in (ROOT / "supabase" / "migrations").glob("*.sql"))
    last = files[-1]
    assert f"`{last}`" in DOC, f"새 SQL {last} 이 안내서 §4 에 없다"
    for name in (f for f in files if f >= "0022"):   # 0022 부터는 한 줄씩(0001~0021 은 한 줄로 묶음)
        assert f"`{name}`" in DOC, name


def test_routes_and_flags_match_the_app():
    web = ROOT / "web" / "app"
    assert "`/start`" in DOC and (web / "start" / "page.tsx").exists()
    assert "`/ops`" in DOC and (web / "ops" / "page.tsx").exists()
    assert "`/settings?op=1`" in DOC and "get('op')" in (ROOT / "web" / "components" / "op-mark.tsx").read_text(encoding="utf-8")
    assert "MULTI=1" in DOC and "MULTI" in (ROOT / "worker" / "link_designer.py").read_text(encoding="utf-8")
