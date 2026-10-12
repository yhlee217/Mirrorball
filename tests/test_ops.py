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
