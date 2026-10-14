"""운영 기록 — 백업 지연·화면 오류 감시(scripts/sync_health_check.py) · 오류 경로 다듬기(web/lib/ops.ts).

감시자가 놓치면 '백업이 몇 주째 안 됐다'를 사고 난 뒤에야 안다. 기한 전엔 경고만, 기한 뒤엔 실패 —
그래야 '맥에 새 코드를 안 깔았다'도 결국 드러난다. 오류 기록엔 손님을 가리키는 id 가 남지 않아야 한다.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)

NOW = dt.datetime(2026, 10, 22, 1, 0, tzinfo=dt.timezone.utc)


def ago(days: float) -> str:
    return (NOW - dt.timedelta(days=days)).isoformat()


def test_backup_and_error_rules():
    rows = [
        {"slug": "a", "last_backup": ago(4), "errors_24h": 0},     # 정상
        {"slug": "b", "last_backup": ago(9), "errors_24h": 1},     # 백업 9일 전
        {"slug": "c", "last_backup": ago(1), "errors_24h": 6},     # 오류 많음
        {"slug": "d", "last_backup": None, "errors_24h": 0},       # 아직 한 번도
    ]
    bad, warn = shc.evaluate_ops(rows, NOW, 8, 5, required=False)
    assert bad == ["b: 마지막 백업 9.0일 전", "c: 지난 24시간 화면 오류 6건"]
    assert warn == ["d: 백업 기록 없음"]                         # 기한 전엔 경고만
    bad, warn = shc.evaluate_ops(rows, NOW, 8, 5, required=True)
    assert "d: 백업 기록 없음" in bad and warn == []              # 기한 뒤엔 실패


def test_names_line_up_with_migration():
    """감시자가 부르는 함수 · 워커가 남기는 kind · 앱이 남기는 kind 가 마이그레이션과 같은 이름."""
    sql = (ROOT / "supabase" / "migrations" / "0023_ops_events.sql").read_text(encoding="utf-8")
    assert "function public.ops_health()" in sql
    assert re.search(r"kind in \('backup', 'error'\)", sql)
    assert '"kind": "backup"' in (ROOT / "worker" / "backup.py").read_text(encoding="utf-8")
    assert "kind: 'error'" in (ROOT / "web" / "app" / "api" / "client-error" / "route.ts").read_text(encoding="utf-8")
    wf = (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8")
    assert "BACKUP_REQUIRED_SINCE" in wf


def test_clean_path_drops_ids():
    got = run_ts(["lib/ops.ts"], """
const { cleanPath } = require('./ops.js');
out(D.paths.map(cleanPath));
""", {"paths": [
        "/customer/3f2b1c9a-1234-4cde-8f00-0123456789ab",
        "/customers?filter=overdue",
        "/p/hayewoni#top",
        "/customer/123456/edit",
        "https://evil.example/x",
        None,
    ]})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    assert got == ["/customer/:id", "/customers", "/p/hayewoni", "/customer/:id/edit", "/", "/"]


# ── 화면 속도 · 매장별 사용(0024, 개선 계획 v7 P0) ─────────────────────────────

def test_clean_timing_keeps_only_path_and_numbers():
    """폰이 보낸 속도 기록 — 경로의 손님 id 는 지우고, 밀리초가 이상하면 버리고, 다른 칸은 남기지 않는다."""
    got = run_ts(["lib/ops.ts"], """
const { cleanTiming } = require('./ops.js');
out(D.bodies.map(cleanTiming));
""", {"bodies": [
        {"path": "/customer/3f2b1c9a-1234-4cde-8f00-0123456789ab", "ms": 1234.6, "cached": False, "first": False,
         "name": "김서연", "phone": "01012345678"},                       # 엉뚱한 칸은 버린다
        {"path": "/alerts?n=100", "ms": 40, "cached": True},
        {"path": "/", "ms": 2100, "first": True},
        {"path": "/stats", "ms": -5},                                    # 음수
        {"path": "/stats", "ms": 61000},                                 # 1분 넘음(폰이 잠겼다 깸)
        {"path": "/stats", "ms": "900"},                                 # 숫자가 아님
        None,
    ]})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    assert got == [
        {"path": "/customer/:id", "ms": 1235, "cached": False, "first": False},
        {"path": "/alerts", "ms": 40, "cached": True, "first": False},
        {"path": "/", "ms": 2100, "cached": False, "first": True},
        None, None, None, None,
    ]


def test_speed_and_usage_lines_are_numbers_only():
    speed = shc.fmt_speed([
        {"screen": "/stats", "opened": 12, "p50_ms": 3210, "p90_ms": 5480, "instant": 2},
        {"screen": "/ (앱 열기)", "opened": 5, "p50_ms": 1800, "p90_ms": 2600, "instant": 0},
        {"screen": "/alerts", "opened": 3, "p50_ms": None, "p90_ms": None, "instant": 3},   # 모두 받아 둔 화면
    ])
    assert speed[0].split() == ["/stats", "보통", "3.2초", "·", "느린", "때", "5.5초", "·", "10번", "(바로", "2번)"]
    assert "보통 1.8초 · 느린 때 2.6초 · 5번" in speed[1] and "바로" not in speed[1]
    assert "기다린 적 없음" in speed[2] and "(바로 3번)" in speed[2]
    usage = shc.fmt_usage([
        {"slug": "hayewoni", "screens_7d": 120, "contacts_7d": 14, "last_seen": (NOW - dt.timedelta(hours=3)).isoformat()},
        {"slug": "juhwan", "screens_7d": 8, "contacts_7d": 0, "last_seen": ago(5)},
        {"slug": "daunbu", "screens_7d": 0, "contacts_7d": 0, "last_seen": None},
    ], NOW)
    assert usage[0].split() == ["hayewoni", "화면", "120번", "·", "연락", "14명", "·", "마지막", "사용", "오늘"]
    assert usage[1].endswith("마지막 사용 5일 전") and usage[2].endswith("마지막 사용 기록 없음")


def test_speed_names_line_up_with_0024():
    """감시자가 부르는 함수 · 앱이 남기는 kind 가 0024 마이그레이션과 같은 이름이고, 앱은 '오류 · 속도'만 남길 수 있다."""
    sql = (ROOT / "supabase" / "migrations" / "0024_speed_usage.sql").read_text(encoding="utf-8")
    assert "function public.ops_speed()" in sql and "function public.ops_usage()" in sql
    assert re.search(r"kind in \('backup', 'error', 'timing'\)", sql)
    assert re.search(r"for insert to authenticated\s+with check \(kind in \('error', 'timing'\)", sql)
    assert "kind: 'timing'" in (ROOT / "web" / "app" / "api" / "client-timing" / "route.ts").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    assert '"ops_speed"' in script and '"ops_usage"' in script
