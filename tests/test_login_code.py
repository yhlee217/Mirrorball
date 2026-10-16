"""새 디자이너 첫 로그인(worker/login_code.py, 개선 계획 v15 P0) — 네트워크 없이.

Supabase 기본 메일은 팀원 주소로만 보내서 디자이너님께 코드가 안 갈 수 있다. 맥에서 계정 · 매장 잇기 · 코드를 한 번에 —
미리보기가 기본이고, 매장 규칙은 link_designer 와 같고, 코드는 화면에만 찍힌다(이메일은 가려서).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import login_code as lc  # noqa: E402

USERS = [
    {"id": "u1", "email": "Juhwan.Kim@Gmail.com", "last_sign_in_at": None},
    {"id": "u2", "email": "hayewoni@naver.com", "last_sign_in_at": "2026-10-15T02:00:00Z"},
]
TENANTS = [
    {"id": "t-h", "slug": "hayewoni"},
    {"id": "t-j", "slug": "juhwan"},
    {"id": "t-d", "slug": "daunbu"},
    {"id": "t-demo", "slug": "demo-1a2b3c4d"},
]


def test_plan_new_account_with_salon(monkeypatch):
    monkeypatch.delenv("MULTI", raising=False)
    p = lc.plan(" Daun.Lee@Naver.com ", "daunbu", USERS, TENANTS, [])
    assert not p["blocked"] and p["create"] and p["link"] and p["tenant_id"] == "t-d" and p["user_id"] is None
    assert p["steps"][0].startswith("d***@n***.com 계정이 없어요")
    assert "daun.lee@naver.com" not in " ".join(p["steps"]).lower()


def test_plan_existing_account_cases(monkeypatch):
    monkeypatch.delenv("MULTI", raising=False)
    already = lc.plan("juhwan.kim@gmail.com", "juhwan", USERS, TENANTS, [{"tenant_id": "t-j"}])
    assert not already["blocked"] and not already["create"] and not already["link"] and already["user_id"] == "u1"
    assert "이미" in already["steps"][0] and "코드를 만듭니다" in already["steps"][-1]
    only_code = lc.plan("juhwan.kim@gmail.com", None, USERS, TENANTS, [])
    assert only_code["steps"] == ["j***@g***.com 의 앱 로그인 코드를 만듭니다(메일은 보내지 않아요)"]
    demo = lc.plan("juhwan.kim@gmail.com", "juhwan", USERS, TENANTS, [{"tenant_id": "t-demo"}])
    assert demo["link"] and "데모 매장 소속은 그대로" in demo["steps"][0]
    other = lc.plan("juhwan.kim@gmail.com", "daunbu", USERS, TENANTS, [{"tenant_id": "t-j"}])
    assert other["blocked"] and "MULTI=1" in other["message"]
    monkeypatch.setenv("MULTI", "1")
    assert lc.plan("juhwan.kim@gmail.com", "daunbu", USERS, TENANTS, [{"tenant_id": "t-j"}])["link"]


def test_plan_stops_on_bad_input():
    no_t = lc.plan("juhwan.kim@gmail.com", "juhwann", USERS, TENANTS, [])
    assert no_t["blocked"] and "daunbu, hayewoni, juhwan" in no_t["message"]
    for bad in ("juhwan", "a@b", "a b@c.com", ""):
        assert lc.plan(bad, None, USERS, TENANTS, [])["blocked"], bad


def test_otp_of_reads_both_shapes():
    assert lc.otp_of({"id": "u1", "email_otp": "123456", "action_link": "https://x"}) == "123456"
    assert lc.otp_of({"properties": {"email_otp": "654321"}, "user": {}}) == "654321"
    assert lc.otp_of({"action_link": "https://x"}) is None and lc.otp_of(None) is None


def _fake(monkeypatch, memberships):
    calls = {"insert": [], "create": [], "code": []}
    fake = types.SimpleNamespace(insert=lambda table, rows: calls["insert"].append((table, rows)))
    monkeypatch.setitem(sys.modules, "supa", fake)
    monkeypatch.setattr(lc.ld, "_users", lambda: USERS)
    monkeypatch.setattr(lc.ld, "_tenants", lambda: TENANTS)
    monkeypatch.setattr(lc.ld, "_memberships", lambda user_id=None: memberships)
    monkeypatch.setattr(lc, "_create_user", lambda email: calls["create"].append(email) or "new-id")
    monkeypatch.setattr(lc, "_login_code", lambda email: calls["code"].append(email) or "482913")
    return calls


def test_preview_writes_nothing(monkeypatch, capsys):
    calls = _fake(monkeypatch, [])
    monkeypatch.delenv("CONFIRM", raising=False)
    assert lc.main(["x", "daun.lee@naver.com", "daunbu"]) == 0
    assert calls == {"insert": [], "create": [], "code": []}
    out = capsys.readouterr().out
    assert "CONFIRM=1" in out and "로그인 코드  " not in out


def test_confirm_creates_links_and_prints_code_only_on_screen(monkeypatch, capsys):
    calls = _fake(monkeypatch, [])
    monkeypatch.setenv("CONFIRM", "1")
    assert lc.main(["x", "Daun.Lee@Naver.com", "daunbu"]) == 0
    assert calls["create"] == ["daun.lee@naver.com"] and calls["code"] == ["daun.lee@naver.com"]
    assert calls["insert"] == [("memberships", [{"tenant_id": "t-d", "user_id": "new-id", "role": "owner"}])]
    out = capsys.readouterr().out
    assert "로그인 코드  482913" in out and "daun.lee@naver.com" not in out.lower()
    src = (ROOT / "worker" / "login_code.py").read_text(encoding="utf-8")
    assert "ops_events" not in src and "open(" not in src and "write_text" not in src   # 코드는 어디에도 남기지 않는다


def test_existing_linked_account_gets_code_without_writes(monkeypatch, capsys):
    calls = _fake(monkeypatch, [{"tenant_id": "t-j"}])
    monkeypatch.setenv("CONFIRM", "1")
    assert lc.main(["x", "juhwan.kim@gmail.com", "juhwan"]) == 0
    assert calls["create"] == [] and calls["insert"] == [] and calls["code"] == ["juhwan.kim@gmail.com"]
    assert lc.main(["x", "juhwan.kim@gmail.com", "nope"]) == 1                                  # 없는 매장 — 코드도 안 냄
    assert calls["code"] == ["juhwan.kim@gmail.com"]
