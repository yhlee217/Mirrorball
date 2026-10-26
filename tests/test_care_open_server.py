"""챙길 고객 펼침 수 · 앱 첫 열기 서버 시간(개선 계획 v16 P1 · P2, 0029).

P1 — 연락이 감시에 잡힌 10.08~26 내내 0. 챙길 고객 화면은 주 3~12번 여는데 줄을 펼쳐 보기는 하는지 몰랐다. 펼친 수만
     센다(어느 손님인지는 없음) — 매일 감시 · /ops 매장 줄에 '챙길 고객 펼침 N번 · 연락 K명'.
P2 — 앱 첫 열기 느린 때 2.7~2.9초(10.19~26). 서버가 첫 바이트를 보낸 시각(브라우저가 이미 잰 값)을 함께 받아
     '— 그중 서버 보통 · 느린 때'. 서버 몫이면 로그인 확인 · 첫 화면 데이터를, 아니면 화면 그리기를 본다.
0029 전에도 앱 · 감시는 지금처럼 돈다(기록만 거절되고, 칸이 없으면 예전 글).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import re
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SQL = (ROOT / "supabase" / "migrations" / "0029_care_open_server.sql").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)

NOW = dt.datetime(2026, 10, 27, 1, 0, tzinfo=dt.timezone.utc)
SINCE = "2026-10-15T06:01:02.123+00:00"
USAGE_0029 = [
    {"slug": "hayewoni", "screens_7d": 36, "app_7d": 36, "op_7d": 4, "contacts_7d": 0, "care_opens_7d": 5,
     "last_seen": (NOW - dt.timedelta(hours=2)).isoformat(), "since": SINCE},
    {"slug": "juhwan", "screens_7d": 0, "app_7d": 0, "op_7d": 0, "contacts_7d": 0, "care_opens_7d": None,
     "last_seen": None, "since": SINCE},
]
SPEED_0029 = [
    {"screen": "/ (앱 열기)", "opened": 11, "p50_ms": 820, "p90_ms": 2910, "instant": 0, "server_p50_ms": 410, "server_p90_ms": 2140},
    {"screen": "/customers", "opened": 4, "p50_ms": 610, "p90_ms": 830, "instant": 0, "server_p50_ms": None, "server_p90_ms": None},
]


def test_clean_care_keeps_no_customer():
    got = run_ts(["lib/ops.ts"], "const { cleanCare } = require('./ops.js'); out(D.map(cleanCare));", [
        {"step": "open", "op": True, "app": True},
        {"step": "open", "customer_id": "3f2b1c9a-1234-4cde-8f00-0123456789ab", "name": "김서연"},   # 보내 와도 버린다
        {"step": "send"}, {"step": "open", "op": "1"}, None, {},
    ])
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    assert got == [{"step": "open", "op": True, "app": True}, {"step": "open", "op": False, "app": False},
                   None, {"step": "open", "op": False, "app": False}, None, None]


def test_clean_timing_takes_server_time_only_on_first_open():
    got = run_ts(["lib/ops.ts"], "const { cleanTiming } = require('./ops.js'); out(D.map(cleanTiming));", [
        {"path": "/", "ms": 2910, "first": True, "server": 2140.4},
        {"path": "/", "ms": 900, "first": True, "server": 1200},          # 전체보다 길다 — 버린다
        {"path": "/", "ms": 900, "first": True, "server": -1},
        {"path": "/", "ms": 900, "first": True, "server": "300"},
        {"path": "/stats", "ms": 700, "first": False, "server": 300},     # 앱 안 이동엔 서버 시간이 없다
    ])
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    assert got[0]["server"] == 2140 and got[0]["ms"] == 2910
    assert all("server" not in g for g in got[1:])


def test_phone_sends_open_once_per_row_and_server_time_on_first_open():
    lst = (WEB / "app" / "alerts" / "alerts-list.tsx").read_text(encoding="utf-8")
    assert "import { sendCareOpen } from '@/components/screen-timer';" in lst
    toggle = lst[lst.index("function toggle(id: string, isOpen: boolean)"):]
    toggle = toggle[:toggle.index("\n  }\n") + 4]
    assert "if (!isOpen && !counted.current.has(id))" in toggle and "sendCareOpen();" in toggle   # 펼칠 때만 · 한 번만
    assert "onClick={() => toggle(it.id, isOpen)}" in lst
    assert lst.count("setOpen(") == 1                                    # 손으로 펼칠 때만 — 주소로 되살린 줄은 안 셈
    timer = (WEB / "components" / "screen-timer.tsx").read_text(encoding="utf-8")
    assert "post('/api/care-event', { step: 'open' });" in timer          # 손님 id 없이
    assert "first: true, server: serverMs() }" in timer
    assert "performance.getEntriesByType('navigation')[0]" in timer and "nav.responseStart" in timer
    route = (WEB / "app" / "api" / "care-event" / "route.ts").read_text(encoding="utf-8")
    assert "cleanCare(await request.json().catch(() => null))" in route and "kind: 'care', detail" in route
    assert route.index("if (!user)") < route.index("insert(")


def test_0029_counts_only_numbers_behind_the_0027_door():
    assert "to_regprocedure('public.ops_allowed(text)') is null" in SQL                      # 0027 없이 돌리면 멈춘다
    assert "check (kind in ('backup', 'error', 'timing', 'csp', 'care'))" in SQL
    assert re.search(r"for insert to authenticated\s+with check \(kind in \('error', 'timing', 'csp', 'care'\)", SQL)
    for fn in ("ops_speed", "ops_usage"):
        body = SQL[SQL.index(f"create function public.{fn}(p_key text default null)"):]
        body = body[:body.index("$$;")]
        assert body.index("if not public.ops_allowed(p_key) then") < body.index("return query"), fn
        assert f"drop function if exists public.{fn}(text);" in SQL
        assert f"revoke all on function public.{fn}(text) from public;" in SQL
        assert f"grant execute on function public.{fn}(text) to anon, authenticated;" in SQL
    usage = SQL[SQL.index("create function public.ops_usage"):]
    assert "o.kind = 'care' and not coalesce((o.detail->>'op')::boolean, false)" in usage      # 운영자 폰은 뺀다
    assert "care_opens_7d bigint" in usage
    speed = SQL[SQL.index("create function public.ops_speed"):]
    assert "order by (e.detail->>'server')::int" in speed and "filter (where e.detail ? 'server')" in speed
    for banned in ("customer_id", "pii", "name", "phone"):
        assert banned not in SQL.split("create function public.ops_speed")[1].split("create function public.ops_usage")[0], banned


def test_watch_and_ops_screen_say_the_same():
    got = run_ts(["lib/ops-view.ts"], """
const V = require('./ops-view.js');
const now = Date.parse(D.now);
out({ usage: D.usage.map((r) => r.slug + ' ' + V.usageLine(r, now)), speed: D.speed.map((r) => r.screen + ' ' + V.speedLine(r)) });
""", {"usage": USAGE_0029, "speed": SPEED_0029, "now": NOW.isoformat()})
    watch_usage = shc.fmt_usage(USAGE_0029, NOW)[1:]
    watch_speed = shc.fmt_speed(SPEED_0029)
    assert watch_usage[0].split()[1:] == ["디자이너", "화면", "36번(앱", "100%)", "·", "챙길", "고객", "펼침", "5번", "·",
                                          "연락", "0명", "·", "마지막", "사용", "오늘", "·", "운영자", "폰", "4번"]
    assert "챙길 고객 펼침 0번" in watch_usage[1]                                       # 숫자가 비어도 0
    assert "보통 0.8초 · 느린 때 2.9초 · 11번 — 그중 서버 보통 0.4초 · 느린 때 2.1초" in watch_speed[0]
    assert "서버" not in watch_speed[1]                                                 # 앱 안 이동 줄엔 없다
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    norm = lambda s: " ".join(s.split())
    assert [norm(x) for x in got["usage"]] == [norm(x) for x in watch_usage]
    assert [norm(x) for x in got["speed"]] == [norm(x) for x in watch_speed]


def test_before_0029_the_lines_stay_as_they_were():
    old = [{k: v for k, v in r.items() if k != "care_opens_7d"} for r in USAGE_0029]
    assert all("펼침" not in l for l in shc.fmt_usage(old, NOW))
    assert all("서버" not in l for l in shc.fmt_speed([{k: v for k, v in r.items() if not k.startswith("server")} for r in SPEED_0029]))
