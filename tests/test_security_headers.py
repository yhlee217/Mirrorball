"""보안 응답 헤더 · CSP(개선 계획 v14 P0 — 한 주 '보고만', v16 P3 — 막기).

손님 이름 · 번호를 보여 주는 앱인데 보안 헤더가 하나도 없었다(2026-10-15). 틀 넣기 금지 · nosniff · Referrer · Permissions ·
HSTS 는 바로, CSP 전체는 한 주 '보고만' — 어긋나면 운영 기록에 남기되(kind 'csp', 0026) 손님 정보는 없이 규칙 · 출처 · 경로만.
10.19~26 어긋남 0 이라 막기로 바꿨다(v16 P3). 보고 길은 그대로 — 막힌 것도 같은 길로 남는다.
'화면 오류'(kind 'error')와 섞이면 매일 감시가 거짓으로 실패한다.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)


def _headers(url: str | None) -> dict:
    if not shutil.which("node"):
        pytest.skip("node 가 없다")
    arg = json.dumps(url)
    out = subprocess.run(
        ["node", "--input-type=module", "-e",
         f"import('./lib/security-headers.mjs').then((m) => console.log(JSON.stringify(m.securityHeaders({arg}))))"],
        cwd=WEB, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return {h["key"]: h["value"] for h in json.loads(out.stdout)}


def test_headers_cover_framing_sniffing_referrer_and_https():
    h = _headers("https://abc.supabase.co/rest/v1")
    assert h["X-Frame-Options"] == "DENY" and h["X-Content-Type-Options"] == "nosniff"
    assert h["Referrer-Policy"] == "same-origin"                               # 손님 주소가 바깥으로 안 샌다
    assert "camera=()" in h["Permissions-Policy"] and "geolocation=()" in h["Permissions-Policy"]
    assert "web-share" not in h["Permissions-Policy"]                          # 카톡 등 공유는 그대로
    assert h["Strict-Transport-Security"].startswith("max-age=")
    assert "Content-Security-Policy-Report-Only" not in h                      # 보고만이 아니라 막는다(v16 P3)
    csp = h["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp                                      # 틀 넣기 금지도 이 안에
    assert "connect-src 'self' https://abc.supabase.co" in csp                 # Supabase 는 출처만
    assert "'unsafe-eval'" not in csp and "report-uri /api/csp-report" in csp
    assert "object-src 'none'" in csp and "base-uri 'self'" in csp
    assert "https://*.supabase.co" in _headers(None)["Content-Security-Policy"]   # 주소가 없을 때


def test_eval_only_for_the_dev_server():
    """next dev 의 바로 고침은 eval 을 쓴다 — 막는 정책에서 개발 서버만 열어 둔다. 배포(production)엔 없다."""
    if not shutil.which("node"):
        pytest.skip("node 가 없다")
    out = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import('./lib/security-headers.mjs').then((m) => console.log(JSON.stringify("
         "[m.contentSecurityPolicy('https://a.supabase.co', true), m.contentSecurityPolicy('https://a.supabase.co', false)])))"],
        cwd=WEB, capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    dev, prod = json.loads(out.stdout)
    assert "script-src 'self' 'unsafe-inline' 'unsafe-eval'" in dev
    assert "'unsafe-eval'" not in prod and "script-src 'self' 'unsafe-inline';" in prod


def test_next_config_puts_headers_on_every_path():
    cfg = (WEB / "next.config.mjs").read_text(encoding="utf-8")
    assert "source: '/:path*', headers: securityHeaders(process.env.NEXT_PUBLIC_SUPABASE_URL)" in cfg
    assert "staleTimes: { dynamic: 180 }" in cfg                               # 전에 있던 설정은 그대로


def test_middleware_sets_headers_itself():
    """Cloudflare(next-on-pages)에선 미들웨어를 거치는 응답에 next.config 헤더가 안 붙는다(로컬 workerd 로 확인 —
    로그인 화면에만 붙고 홈 · 설정 · API 엔 없었다). 미들웨어가 직접 붙여야 모든 화면에 붙는다."""
    mw = (WEB / "middleware.ts").read_text(encoding="utf-8")
    assert "import { securityHeaders } from './lib/security-headers.mjs';" in mw
    assert "for (const h of SECURITY) response.headers.set(h.key, h.value);" in mw
    body = mw[mw.index("export async function middleware"):]
    assert body.index("response.headers.set(h.key, h.value)") < body.index("return response;")   # 마지막 응답에


def test_csp_reports_keep_only_rule_origin_and_path():
    got = run_ts(["lib/ops.ts"], """
const { cleanCsp, blockedOf } = require('./ops.js');
out({
  browser: cleanCsp({ 'csp-report': { 'document-uri': 'https://app.example/customer/3f2b1c9a-1234-4cde-8f00-0123456789ab?x=1',
    'effective-directive': 'script-src-elem', 'blocked-uri': 'https://static.cloudflareinsights.com/beacon.min.js?token=abc' } }),
  watch: cleanCsp({ directive: 'img-src', blocked: 'data', path: '/visits' }),
  legacy: cleanCsp({ 'csp-report': { 'violated-directive': 'style-src-attr \\'self\\'', 'blocked-uri': 'inline', 'document-uri': '/' } }),
  junk: [cleanCsp(null), cleanCsp({ directive: 'x; drop table', blocked: 'a' }), cleanCsp({})],
  blocked: [blockedOf('eval'), blockedOf('blob:https://a.b/123'), blockedOf(''), blockedOf('not a url'), blockedOf(5)],
});
""", {})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got["browser"] == {"directive": "script-src-elem", "blocked": "https://static.cloudflareinsights.com", "path": "/customer/:id"}
    assert got["watch"] == {"directive": "img-src", "blocked": "data", "path": "/visits"}
    assert got["legacy"] == {"directive": "style-src-attr", "blocked": "inline", "path": "/"}
    assert got["junk"] == [None, None, None]
    assert got["blocked"] == ["eval", "blob", "unknown", "unknown", "unknown"]


def test_report_route_and_listener_and_0026_line_up():
    route = (WEB / "app" / "api" / "csp-report" / "route.ts").read_text(encoding="utf-8")
    assert "cleanCsp(body)" in route and "kind: 'csp'" in route and "status: 204" in route
    assert "text.length > 8000" in route                                       # 큰 보고는 받지 않는다
    assert "<CspWatch />" in (WEB / "app" / "layout.tsx").read_text(encoding="utf-8")
    sql = (ROOT / "supabase" / "migrations" / "0026_csp_reports.sql").read_text(encoding="utf-8")
    assert re.search(r"kind in \('backup', 'error', 'timing', 'csp'\)", sql)
    assert re.search(r"for insert to authenticated\s+with check \(kind in \('error', 'timing', 'csp'\)", sql)
    assert "grant execute on function public.ops_csp() to anon, authenticated;" in sql
    health = (ROOT / "supabase" / "migrations" / "0023_ops_events.sql").read_text(encoding="utf-8")
    assert "e.kind = 'error' and e.created_at > now() - interval '24 hours'" in health   # 오류 기준은 'error' 만 센다
    script = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    assert '"ops_csp"' in script and "report_csp(url, key)" in script
    assert "supabase.rpc('ops_csp')" in (WEB / "app" / "ops" / "page.tsx").read_text(encoding="utf-8")


def test_daily_watch_prints_csp_lines():
    assert shc.fmt_csp([]) == ["  어긋남 없음"]
    line = shc.fmt_csp([{"directive": "script-src-elem", "blocked": "https://static.cloudflareinsights.com", "n": 3}])[0]
    assert line.split() == ["script-src-elem", "https://static.cloudflareinsights.com", "3번"]
