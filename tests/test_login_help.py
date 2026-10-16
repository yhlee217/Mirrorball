"""로그인이 막혔을 때의 말과 길(개선 계획 v15 P0) — 오류는 한국어로 · 운영자 코드로 들어오는 길 · 메일 양식엔 코드만.

Supabase 기본 메일은 팀원 주소로만 보내고(다른 주소는 'not authorized'), 기본 양식엔 코드가 없다. 디자이너님 화면엔
영어 오류 대신 '운영자에게 코드를 받아 넣어 달라'가 떠야 하고, 그 코드를 넣는 길이 늘 열려 있어야 한다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_errors_read_in_korean_and_point_to_the_operator():
    got = run_ts(["lib/login-errors.ts"], """
const { sendError, verifyError } = require('./login-errors.js');
out({ send: D.send.map(sendError), verify: D.verify.map(verifyError) });
""", {
        "send": [
            {"message": 'Email address "daun@naver.com" not authorized', "status": 400, "code": "email_address_not_authorized"},
            {"message": "For security purposes, you can only request this after 52 seconds.", "status": 429,
             "code": "over_email_send_rate_limit"},
            {"message": "email rate limit exceeded", "status": 429},
            {"message": "Unable to validate email address: invalid format", "status": 400, "code": "validation_failed"},
            {"message": "Signups not allowed for otp", "status": 422, "code": "otp_disabled"},
            {"message": "Internal Server Error", "status": 500},
            None,
        ],
        "verify": [
            {"message": "Token has expired or is invalid", "status": 403, "code": "otp_expired"},
            {"message": "Request rate limit reached", "status": 429, "code": "over_request_rate_limit"},
            {"message": "something else", "status": 500},
        ],
    })
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    s, v = got["send"], got["verify"]
    assert s[0].startswith("이 주소로는 아직 메일을 보낼 수 없어요") and "운영자에게 로그인 코드" in s[0]
    assert s[1].startswith("메일을 너무 자주") and s[2] == s[1]
    assert s[3] == "이메일 주소를 다시 확인해 주세요."
    assert s[4].startswith("아직 등록되지 않은 이메일") and "운영자" in s[4]
    assert s[5].startswith("메일을 보내지 못했어요") and s[6] == s[5]
    assert v[0].startswith("코드가 맞지 않거나 시간이 지났어요")
    assert v[1].startswith("너무 여러 번") and v[2].startswith("로그인하지 못했어요")
    for msg in s + v:
        assert not re.search(r"[A-Za-z]", msg), msg                                           # 영어가 섞이지 않는다


def test_login_page_uses_korean_errors_and_keeps_the_code_path():
    src = (WEB / "app" / "login" / "page.tsx").read_text(encoding="utf-8")
    assert "import { sendError, verifyError } from '@/lib/login-errors';" in src
    assert "setErr(sendError(error));" in src and "setErr(verifyError(error));" in src
    assert "setErr(error.message" not in src                                                   # 영어 그대로는 없다
    assert "setStep('code');" in src.split("async function send")[1].split("async function verify")[0]   # 실패해도 코드 단계로
    assert "type: 'magiclink'" in src                                                          # 맥에서 만든 코드도 받는다
    assert "운영자에게 코드를 받아 넣어도 돼요" in src and "코드를 이미 받았다면 입력하기" in src
    start = (WEB / "app" / "start" / "page.tsx").read_text(encoding="utf-8")
    assert "메일이 안 오면 스팸함을 보거나, 운영자에게 코드를 받아" in start


def test_email_templates_carry_only_the_code():
    folder = ROOT / "supabase" / "email_templates"
    for name in ("confirm_signup.html", "magic_link.html"):
        html = (folder / name).read_text(encoding="utf-8")
        assert "{{ .Token }}" in html, name
        for banned in ("ConfirmationURL", "TokenHash", "href", "SiteURL"):                    # 링크는 사파리로 새서 뺀다
            assert banned not in html, (name, banned)
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert "Confirm signup" in readme and "Magic Link" in readme and "worker/login_code.py" in readme
