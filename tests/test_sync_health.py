"""수집 지연 판정 — 앱(web/lib/sync.ts)과 감시자(scripts/sync_health_check.py)가
같은 기준을 써야 한다. 두 벌로 관리하면 한쪽만 고치고 다른 쪽은 조용히 어긋난다.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "sync_health_check", ROOT / "scripts" / "sync_health_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


shc = _load()


def test_threshold_matches_app():
    """앱의 isSyncStale 임계값과 같은지 — 다르면 '앱은 경고, 감시자는 조용' 같은 꼴이 난다."""
    ts = (ROOT / "web" / "lib" / "sync.ts").read_text(encoding="utf-8")
    m = re.search(r"daysAgo\s*>=\s*(\d+)", ts)
    assert m, "web/lib/sync.ts 에서 isSyncStale 임계값을 못 찾음"
    assert int(m.group(1)) == shc.DEFAULT_STALE_DAYS


@pytest.mark.parametrize("days, late", [
    (0, False),
    (6, False),
    (7, False),     # 일요일 수집 직전 — 정상 범위의 최대
    (7.9, False),
    (8, True),      # 예정된 일요일이 통째로 빔
    (35, True),
])
def test_evaluate_boundary(days, late):
    rows = [{"slug": "daunbu", "days_since": days}]
    assert bool(shc.evaluate(rows, shc.DEFAULT_STALE_DAYS)) is late


def test_never_succeeded_is_late():
    """성공 기록이 없는 테넌트(에러 행만 있음)를 조용히 넘기면 설치 직후 실패를 영원히 모른다."""
    rows = [{"slug": "neu", "days_since": None, "last_ok": None}]
    assert len(shc.evaluate(rows, shc.DEFAULT_STALE_DAYS)) == 1


def test_only_late_tenants_returned():
    rows = [
        {"slug": "a", "days_since": 1},
        {"slug": "b", "days_since": 40},
        {"slug": "c", "days_since": 9},
    ]
    assert {r["slug"] for r in shc.evaluate(rows, shc.DEFAULT_STALE_DAYS)} == {"b", "c"}


def test_workflow_runs_on_default_branch_schedule():
    """스케줄 워크플로는 기본 브랜치에서만 돈다 — cron 과 수동 실행이 다 있는지만 확인."""
    y = (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8")
    assert "schedule:" in y and "cron:" in y
    assert "workflow_dispatch" in y
