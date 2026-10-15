"""운영 안내서(playbook/OPERATIONS_APP.md, 개선 계획 v13 P2) — 적힌 명령 · 경로 · SQL 파일이 실제와 같다.

안내서가 낡으면 운영자가 없는 스크립트를 돌리거나 SQL 하나를 빠뜨린다. 파일 이름이 바뀌면 여기서 걸린다.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "playbook" / "OPERATIONS_APP.md").read_text(encoding="utf-8")
WD = "월화수목금토일"


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


def test_weekdays_match_the_calendar():
    """요일을 틀리게 적으면 운영자가 하루 늦게 움직인다 — 2026-10-15 까지 '10.19 일요일'로 적혀 있었다(10.19 는 월요일,
    첫 백업 일요일은 10.18). 계획서의 'M.DD 일요일'은 머리말 날짜의 해로 본다."""
    for y, m, d, wd in re.findall(r"(\d{4})-(\d{2})-(\d{2}) ([월화수목금토일])요일", DOC):
        assert WD[dt.date(int(y), int(m), int(d)).weekday()] == wd, f"{y}-{m}-{d} 은 {wd}요일이 아니다"
    for p in sorted((ROOT / "playbook").glob("IMPROVE_PLAN_v*.md")):
        text = p.read_text(encoding="utf-8")
        year = int(re.search(r"^> (\d{4})-\d{2}-\d{2}", text, re.M).group(1))
        pairs = re.findall(r"(\d{1,2})\.(\d{1,2}) 일요일", text) + re.findall(r"일요일\((\d{1,2})\.(\d{1,2})\)", text)
        for m, d in pairs:
            assert dt.date(year, int(m), int(d)).weekday() == 6, f"{p.name}: {m}.{d} 은 일요일이 아니다"


def test_first_backup_sunday_comes_before_the_watch_requires_it():
    found = re.search(r"\*\*(\d{4}-\d{2}-\d{2}) 일요일 14시 수집 전에", DOC)
    if not found:                                    # 첫 백업이 지나 안내서에서 빠졌으면 볼 것이 없다
        return
    since = re.search(r"BACKUP_REQUIRED_SINCE: '(\d{4}-\d{2}-\d{2})'",
                      (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8"))
    sunday = dt.date.fromisoformat(found.group(1))
    assert sunday.weekday() == 6 and sunday < dt.date.fromisoformat(since.group(1))
