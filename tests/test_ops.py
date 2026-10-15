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
        {"path": "/visits", "ms": 700, "op": True, "app": True},         # v10 P0 — 운영자 폰 · 홈 화면 앱
        {"path": "/visits", "ms": 700, "op": "1", "app": 1},             # 참/거짓이 아니면 '아님'
    ]})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    no = {"op": False, "app": False}  # 두 칸은 늘 남긴다 — 감시(0025)가 이 칸이 있는 기록부터 센다
    assert got == [
        {"path": "/customer/:id", "ms": 1235, "cached": False, "first": False, **no},
        {"path": "/alerts", "ms": 40, "cached": True, "first": False, **no},
        {"path": "/", "ms": 2100, "cached": False, "first": True, **no},
        None, None, None, None,
        {"path": "/visits", "ms": 700, "cached": False, "first": False, "op": True, "app": True},
        {"path": "/visits", "ms": 700, "cached": False, "first": False, **no},
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


# ── 사용 수는 디자이너 것만(0025, 개선 계획 v10 P0) ──────────────────────────────

def test_usage_lines_split_operator_phone_and_show_since():
    """0025 뒤 — 디자이너 화면(그중 앱 비율) · 운영자 폰은 따로 · 맨 위 기록 시작. 0024 모양이면 예전 그대로(위 테스트)."""
    since = "2026-10-15T06:01:02.123+00:00"
    usage = shc.fmt_usage([
        {"slug": "daunbu", "screens_7d": 0, "app_7d": 0, "op_7d": 0, "contacts_7d": 0, "last_seen": None, "since": since},
        {"slug": "hayewoni", "screens_7d": 12, "app_7d": 10, "op_7d": 35, "contacts_7d": 0,
         "last_seen": (NOW - dt.timedelta(hours=2)).isoformat(), "since": since},
        {"slug": "juhwan", "screens_7d": 3, "app_7d": 0, "op_7d": 0, "contacts_7d": 2, "last_seen": ago(2), "since": since},
    ], NOW)
    assert usage[0] == "  화면 기록 10.15 15:01부터 · 운영자 폰은 따로 셈"          # KST
    assert usage[1].split() == ["daunbu", "디자이너", "화면", "0번", "·", "연락", "0명", "·", "마지막", "사용", "기록", "없음"]
    assert usage[2].endswith("디자이너 화면 12번(앱 83%) · 연락 0명 · 마지막 사용 오늘 · 운영자 폰 35번")
    assert usage[3].endswith("디자이너 화면 3번(앱 0%) · 연락 2명 · 마지막 사용 2일 전")   # 운영자 폰 0번은 안 찍는다
    empty = shc.fmt_usage([{"slug": "x", "screens_7d": 0, "app_7d": 0, "op_7d": 0, "contacts_7d": 0,
                            "last_seen": None, "since": None}], NOW)
    assert empty[0] == "  화면 기록 — 새 앱의 기록이 아직 없음(운영자 폰은 따로 셈)"


def test_usage_names_line_up_with_0025():
    """감시 함수가 돌려주는 칸 · 앱이 보내는 두 칸 · 운영자 폰 표시가 서로 같은 이름이다."""
    sql = (ROOT / "supabase" / "migrations" / "0025_usage_designer.sql").read_text(encoding="utf-8")
    assert "drop function if exists public.ops_usage();" in sql            # 돌려주는 칸이 바뀌어 replace 로는 안 된다
    for col in ("screens_7d", "app_7d", "op_7d", "contacts_7d", "last_seen", "since"):
        assert re.search(rf"^\s+{col}\s+(bigint|timestamptz)", sql, re.M), col
    assert "e.detail ? 'op'" in sql and "detail->>'app'" in sql            # 두 칸이 있는 기록부터
    assert "grant execute on function public.ops_usage() to anon, authenticated;" in sql
    script = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    assert '"op_7d"' in script and '"app_7d"' in script and '"since"' in script
    timer = (ROOT / "web" / "components" / "screen-timer.tsx").read_text(encoding="utf-8")
    assert "op: isOp(), app: isApp()" in timer and "export const OP_KEY = 'mb-op';" in timer
    mark = (ROOT / "web" / "components" / "op-mark.tsx").read_text(encoding="utf-8")
    assert "OP_KEY" in mark and "get('op')" in mark
    assert "<OpMark />" in (ROOT / "web" / "app" / "settings" / "page.tsx").read_text(encoding="utf-8")
