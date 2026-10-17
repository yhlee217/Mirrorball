"""운영 숫자 문단속(0027, 개선 계획 v15 P2) — 공개 키로는 안 보이게.

운영 숫자 함수 다섯이 공개 키(anon)로 열려 있어, 앱 코드에 든 공개 키만으로 누구나 매장별 사용 · 연락 수를 받아 갈 수
있었다. 0027 뒤엔 운영자 계정이거나 감시 열쇠(DB 엔 해시만)가 맞을 때만 준다. 매일 감시는 열쇠를 본문으로 넘기고,
0027 전 함수엔 예전처럼 부른다. 실제 Postgres 로 0001~0027 을 올려 거절 · 허용 · 같은 숫자를 따로 확인했다(v15 §6).
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import urllib.error
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SQL = (ROOT / "supabase" / "migrations" / "0027_ops_lock.sql").read_text(encoding="utf-8")
FNS = ("sync_health", "ops_health", "ops_speed", "ops_usage", "ops_csp")
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)


def _body(fn: str) -> str:
    start = SQL.index(f"create or replace function public.{fn}(p_key text default null)")
    return SQL[start:SQL.index("\n$$;", start)]


def test_every_ops_function_checks_the_door_first():
    for fn in FNS:
        assert f"drop function if exists public.{fn}();" in SQL, fn                     # 인자 없는 옛 함수는 지운다
        body = _body(fn)
        door = body.index("if not public.ops_allowed(p_key) then")
        assert door < body.index("return query"), fn                                        # 문부터 — 그 뒤에 숫자
        assert "using errcode = '42501'" in body[door:body.index("return query")], fn
        assert f"grant execute on function public.{fn}(text) to anon, authenticated;" in SQL, fn
        assert f"revoke all on function public.{fn}(text) from public;" in SQL, fn


def test_keys_are_stored_as_hashes_and_admin_functions_are_closed():
    assert "encode(sha256(convert_to(k, 'UTF8')), 'hex')" in SQL                            # 만든 열쇠는 해시로만
    assert "encode(sha256(convert_to(p_key, 'UTF8')), 'hex')" in SQL                        # 들어온 열쇠도 해시로 비교
    assert "coalesce(length(p_key), 0) >= 32" in SQL                                       # 짧은 값은 보지도 않는다
    assert not re.search(r"insert into public\.ops_watch_keys \(hash\) values \(k\)", SQL)  # 원문을 넣지 않는다
    for fn in ("ops_new_watch_key()", "ops_add_reader(text)", "ops_allowed(text)"):
        assert f"revoke all on function public.{fn} from public, anon, authenticated;" in SQL, fn
    assert "grant execute on function public.ops_is_reader() to authenticated;" in SQL
    for t in ("ops_readers", "ops_watch_keys"):
        assert f"alter table public.{t} enable row level security;" in SQL
        assert f"revoke all on public.{t} from anon, authenticated;" in SQL
        assert not re.search(rf"create policy \w+ on public\.{t}", SQL)                   # 정책 없음 — API 로는 못 본다


def test_bodies_match_the_earlier_migrations():
    """세는 법은 그대로 — 0022~0026 의 핵심 줄이 0027 몸통에도 있다(실제 숫자 비교는 임시 Postgres 로)."""
    checks = {
        "sync_health": ["max(j.finished_at) filter (where j.status = 'ok')", "join public.tenants t on t.id = j.tenant_id"],
        "ops_health": ["count(e.id) filter (where e.kind = 'error' and e.created_at > now() - interval '24 hours')"],
        "ops_speed": ["where e.kind = 'timing' and e.created_at > now() - interval '7 days'", "then (e.detail->>'path') || ' (앱 열기)'"],
        "ops_usage": ["where e.kind = 'timing' and e.detail ? 'op'", "c.kind = 'contact' and c.sent_at > now() - interval '7 days'"],
        "ops_csp": ["where e.kind = 'csp' and e.created_at > now() - interval '7 days'", "limit 20"],
    }
    for fn, lines in checks.items():
        for line in lines:
            assert line in _body(fn), (fn, line)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(calls, answers):
    def urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        calls.append(body)
        code = answers(body)
        if code != 200:
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b"{}"))
        return _Resp(b"[]")
    return urlopen


@pytest.mark.parametrize("watch,answers,want_calls,raises", [
    ("", lambda b: 200, [{}], False),                                                      # 열쇠 없음 — 예전처럼
    ("k" * 64, lambda b: 200, [{"p_key": "k" * 64}], False),                               # 0027 뒤 — 본문으로
    ("k" * 64, lambda b: 404 if "p_key" in b else 200, [{"p_key": "k" * 64}, {}], False),  # 0027 전 함수 — 다시 빈 본문
    ("k" * 64, lambda b: 401, [{"p_key": "k" * 64}], True),                                # 틀린 열쇠 — 빈 본문으로 새지 않는다
])
def test_watch_sends_the_key_in_the_body(monkeypatch, watch, answers, want_calls, raises):
    calls: list = []
    monkeypatch.setenv("OPS_WATCH_KEY", watch)
    monkeypatch.setattr(shc.urllib.request, "urlopen", _fake_urlopen(calls, answers))
    if raises:
        with pytest.raises(urllib.error.HTTPError):
            shc.fetch("https://x.supabase.co", "anon", "ops_usage")
    else:
        assert shc.fetch("https://x.supabase.co", "anon", "ops_usage") == []
    assert calls == want_calls


def test_watch_workflow_passes_the_key_and_explains_a_locked_door():
    wf = (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8")
    assert "OPS_WATCH_KEY: ${{ secrets.OPS_WATCH_KEY }}" in wf and "SUPABASE_SERVICE_ROLE_KEY" not in wf
    assert "OPS_WATCH_KEY" in shc.LOCKED and "§4" in shc.LOCKED
    src = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    assert src.count("LOCKED if exc.code in (401, 403)") == 4                               # 운영 기록 · 속도 · CSP · DB 용량


def test_app_gate_falls_back_to_the_cookie_only_before_0027():
    got = run_ts(["lib/ops-gate.ts"], """
const { canSeeOps } = require('./ops-gate.js');
const fake = (r) => ({ rpc: async (fn) => (fn === 'ops_is_reader' ? r : { data: null, error: { code: 'x' } }) });
(async () => out(await Promise.all([
  canSeeOps(fake({ data: true, error: null }), false),
  canSeeOps(fake({ data: false, error: null }), true),
  canSeeOps(fake({ data: null, error: { code: 'PGRST202' } }), true),
  canSeeOps(fake({ data: null, error: { code: 'PGRST202' } }), false),
])))();
""", {})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got == [True, False, True, False]   # 운영자 계정 · 쿠키만으론 안 됨(0027 뒤) · 0027 전엔 쿠키대로
