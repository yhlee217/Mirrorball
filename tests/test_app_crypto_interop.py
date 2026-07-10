"""app_crypto(파이썬) ↔ <appcrypto>(JS/브라우저) 상호호환.

파이썬이 암호화한 봉투를 실제 브라우저 Web Crypto 로 복호화해, 배포 데이터를 앱이
실제로 열 수 있음을 보장(암호화 알고리즘·파라미터 불일치 회귀 차단). crypto.subtle 는
보안 컨텍스트가 필요하므로 127.0.0.1 로컬 HTTP 서버로 페이지를 제공한다. playwright 없으면 skip.
"""

import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app_crypto

INDEX = ROOT / "app" / "index.html"


def _appcrypto_js():
    m = re.search(r"//\s*<appcrypto>(.*?)//\s*</appcrypto>", INDEX.read_text(encoding="utf-8"), re.S)
    assert m, "index.html 에서 <appcrypto> 마커를 찾지 못함"
    assert "function decryptEnvelope" in m.group(1)
    return m.group(1)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<!doctype html><html><body></body></html>")

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def base_url():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@pytest.fixture(scope="module")
def page(base_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium 실행 불가: {exc}")
        pg = b.new_page()
        pg.goto(base_url)                     # 127.0.0.1 = 보안 컨텍스트 → crypto.subtle 사용 가능
        pg.add_script_tag(content=_appcrypto_js())
        yield pg
        b.close()


def test_python_encrypt_browser_decrypt(page):
    payload = json.dumps({"slug": "hayewoni", "designer": "하예원",
                          "clients": [{"name": "강유신", "total_won": 128000}]}, ensure_ascii=False)
    env = app_crypto.encrypt_text(payload, "salon-secret-2026", iterations=50000)
    out = page.evaluate("async (a)=>await decryptEnvelope(a.env, a.pw)",
                        {"env": env, "pw": "salon-secret-2026"})
    obj = json.loads(out)
    assert obj["designer"] == "하예원"
    assert obj["clients"][0]["name"] == "강유신"


def test_browser_is_envelope(page):
    env = app_crypto.encrypt_text("{}", "pw", iterations=1000)
    assert page.evaluate("(e)=>isEnvelope(e)", env) is True
    assert page.evaluate("(o)=>isEnvelope(o)", {"slug": "x", "clients": []}) is False


def test_wrong_passphrase_rejects_in_browser(page):
    env = app_crypto.encrypt_text('{"x":1}', "correct", iterations=50000)
    with pytest.raises(Exception):     # 틀린 비번 → decryptEnvelope reject → evaluate 예외
        page.evaluate("async (a)=>await decryptEnvelope(a.env, a.pw)", {"env": env, "pw": "wrong"})
