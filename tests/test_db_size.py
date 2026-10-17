"""DB 용량(0028, 2026-10-17 운영자 질문) — 무료 한도(500MB)에 다가가면 미리 알기.

Supabase 무료 플랜은 DB 가 500MB 를 넘으면 읽기 전용이 된다 — 앱 저장 · 일요일 수집 · 백업이 모두 막힌다. 그런데
매일 감시는 용량을 보지 않아 수집이 8일 밀린 뒤에야 알았다. 매일 용량을 찍고 400MB(80%)를 넘으면 실패(메일),
운영 숫자 화면에도 같은 글. 0027 과 같은 문(운영자 계정 · 감시 열쇠)으로만 열린다. 실제 Postgres 로 따로 확인했다.
"""

from __future__ import annotations

import importlib.util
import io
import urllib.error
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SQL = (ROOT / "supabase" / "migrations" / "0028_db_size.sql").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)

MB = 1048576
SMALL = [{"part": "total", "bytes": int(52.3 * MB)}, {"part": "customers", "bytes": int(4.25 * MB)},
         {"part": "transactions", "bytes": int(12.6 * MB)}, {"part": "ops_events", "bytes": 300_000}]
BIG = [{"part": "total", "bytes": 431 * MB}, {"part": "ops_events", "bytes": 260 * MB}]


def test_function_opens_only_through_the_0027_door():
    body = SQL[SQL.index("create or replace function public.ops_db_size"):]
    assert body.index("if not public.ops_allowed(p_key) then") < body.index("return query")
    assert "using errcode = '42501'" in body
    assert "pg_database_size(current_database())" in body and "pg_total_relation_size(c.oid)" in body
    assert "n.nspname = 'public' and c.relkind = 'r'" in body and "limit 5" in body      # 표 이름 · 크기만
    assert "revoke all on function public.ops_db_size(text) from public;" in SQL
    assert "grant execute on function public.ops_db_size(text) to anon, authenticated;" in SQL
    for banned in ("pii", "customers.", "from public.customers", "select *"):
        assert banned not in body, banned


def test_watch_lines_and_threshold():
    lines, bad = shc.fmt_db_size(SMALL)
    assert lines[0].strip() == "전체 52MB / 무료 500MB (10%)" and bad == []
    assert lines[1].strip() == "큰 표: transactions 13MB · customers 4.3MB · ops_events 0.3MB"   # 큰 것부터
    lines, bad = shc.fmt_db_size(BIG)
    assert lines[0].strip() == "전체 431MB / 무료 500MB (86%) · 경고 400MB 넘음"
    assert bad == ["DB 용량 431MB — 무료 한도 500MB 의 86%(경고 400MB)"]
    assert shc.fmt_db_size(BIG, limit_mb=8192, warn_mb=6554)[1] == []                       # Pro 로 올리면 기준만 바꾼다
    assert shc.fmt_db_size([{"part": "ops_events", "bytes": 1}])[1] == []                   # 전체 줄이 없으면 실패로 안 침
    assert shc.mb_text(int(9.96 * MB)) == "10.0MB" and shc.mb_text(0) == "0.0MB"


def test_ops_screen_says_the_same_as_the_watch():
    got = run_ts(["lib/ops-view.ts"], """
const V = require('./ops-view.js');
out({ small: V.dbLines(D.small), big: V.dbLines(D.big), none: V.dbLines([]), limit: V.DB_LIMIT_MB, warn: V.DB_WARN_MB,
      mb: [V.mbText(D.edge), V.mbText(0)] });
""", {"small": SMALL, "big": BIG, "edge": int(9.96 * MB)})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["small"] == [l.strip() for l in shc.fmt_db_size(SMALL)[0]]
    assert got["big"] == [l.strip() for l in shc.fmt_db_size(BIG)[0]]
    assert got["none"] == ["용량을 못 읽었다(전체 줄 없음)"]
    assert (got["limit"], got["warn"]) == (shc.DEFAULT_DB_LIMIT_MB, shc.DEFAULT_DB_WARN_MB)
    assert got["mb"] == ["10.0MB", "0.0MB"]


def _http(code):
    return urllib.error.HTTPError("https://x", code, "x", {}, io.BytesIO(b"{}"))


def test_report_fails_only_over_the_line(monkeypatch, capsys):
    def fetch_with(result):
        def fake(url, key, fn="sync_health"):
            assert fn == "ops_db_size"
            if isinstance(result, Exception):
                raise result
            return result
        return fake

    monkeypatch.delenv("DB_WARN_MB", raising=False)
    monkeypatch.delenv("DB_LIMIT_MB", raising=False)
    monkeypatch.setattr(shc, "fetch", fetch_with(SMALL))
    assert shc.report_db_size("u", "k") == [] and "전체 52MB / 무료 500MB (10%)" in capsys.readouterr().out
    monkeypatch.setattr(shc, "fetch", fetch_with(BIG))
    assert shc.report_db_size("u", "k") and "§6 'DB 용량'" in capsys.readouterr().out
    monkeypatch.setattr(shc, "fetch", fetch_with(_http(404)))
    assert shc.report_db_size("u", "k") == [] and "0028_db_size.sql" in capsys.readouterr().out   # 0028 전 — 한 줄만
    monkeypatch.setattr(shc, "fetch", fetch_with(_http(401)))
    assert shc.report_db_size("u", "k") == [] and "OPS_WATCH_KEY" in capsys.readouterr().out
    monkeypatch.setenv("DB_WARN_MB", "500")
    monkeypatch.setattr(shc, "fetch", fetch_with(BIG))
    assert shc.report_db_size("u", "k") == []                                                   # 기준은 환경 값으로


def test_watch_main_page_and_workflow_are_wired():
    src = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    main = src[src.index("def main"):]
    assert "size_bad = report_db_size(url, key)" in main and "not late and not ops_bad and not size_bad" in main
    wf = (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8")
    assert f"DB_LIMIT_MB: '{shc.DEFAULT_DB_LIMIT_MB}'" in wf and f"DB_WARN_MB: '{shc.DEFAULT_DB_WARN_MB}'" in wf
    page = (WEB / "app" / "ops" / "page.tsx").read_text(encoding="utf-8")
    assert "supabase.rpc('ops_db_size')" in page and "dbLines(" in page
    assert page.index("canSeeOps(supabase, opCookie)") < page.index("supabase.rpc('ops_db_size')")   # 문부터
