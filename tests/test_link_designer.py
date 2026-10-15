"""디자이너 연결(worker/link_designer.py, 개선 계획 v13 P0) — 네트워크 없이.

매장을 잘못 이으면 남의 손님이 보인다. 미리보기가 기본이고, 없는 계정 · 없는 매장은 막고, 이미 다른 실제 매장에 이어진
계정은 MULTI=1 없이는 잇지 않는다. 출력엔 이메일이 가려서만 나온다.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import link_designer as ld  # noqa: E402

USERS = [
    {"id": "u1", "email": "Juhwan.Kim@Gmail.com", "last_sign_in_at": "2026-10-16T01:00:00Z"},
    {"id": "u2", "email": "hayewoni@naver.com", "last_sign_in_at": "2026-10-15T02:00:00Z"},
    {"id": "u3", "email": "owner@example.com", "last_sign_in_at": None},
]
TENANTS = [
    {"id": "t-h", "slug": "hayewoni"},
    {"id": "t-j", "slug": "juhwan"},
    {"id": "t-d", "slug": "daunbu"},
    {"id": "t-demo", "slug": "demo-1a2b3c4d"},
]


def test_mask_email_hides_but_stays_recognizable():
    assert ld.mask_email("juhwan.kim@gmail.com") == "j***@g***.com"
    assert ld.mask_email("a@b") == "a***@b***"
    assert ld.mask_email(None) == "(이메일 없음)"


def test_decide_covers_every_case():
    d = ld.decide
    assert d("nobody@x.com", "juhwan", USERS, TENANTS, [])["action"] == "no_user"
    no_t = d("juhwan.kim@gmail.com", "juhwann", USERS, TENANTS, [])
    assert no_t["action"] == "no_tenant" and "daunbu, hayewoni, juhwan" in no_t["message"]    # 데모는 안 보여 준다
    link = d("  JUHWAN.kim@gmail.com ", "juhwan", USERS, TENANTS, [])                         # 대소문자 · 띄어쓰기
    assert link["action"] == "link" and link["user_id"] == "u1" and link["tenant_id"] == "t-j"
    demo = d("juhwan.kim@gmail.com", "juhwan", USERS, TENANTS, [{"tenant_id": "t-demo"}])
    assert demo["action"] == "link" and "데모 매장 소속은 그대로" in demo["message"]
    assert d("juhwan.kim@gmail.com", "juhwan", USERS, TENANTS, [{"tenant_id": "t-j"}])["action"] == "already"
    other = d("juhwan.kim@gmail.com", "daunbu", USERS, TENANTS, [{"tenant_id": "t-j"}])
    assert other["action"] == "other_salon" and other["others"] == ["juhwan"] and "MULTI=1" in other["message"]
    for r in (link, demo, other, no_t):
        assert "juhwan.kim@gmail.com" not in r["message"].lower()                            # 이메일은 가려서만


def _fake(monkeypatch, memberships):
    inserted = []
    fake = types.SimpleNamespace(insert=lambda table, rows: inserted.append((table, rows)))
    monkeypatch.setitem(sys.modules, "supa", fake)
    monkeypatch.setattr(ld, "_users", lambda: USERS)
    monkeypatch.setattr(ld, "_tenants", lambda: TENANTS)
    monkeypatch.setattr(ld, "_memberships", lambda user_id=None: memberships)
    return inserted


def test_preview_by_default_and_link_with_confirm(monkeypatch, capsys):
    inserted = _fake(monkeypatch, [])
    monkeypatch.delenv("CONFIRM", raising=False)
    assert ld.main(["x", "juhwan.kim@gmail.com", "juhwan"]) == 0 and inserted == []          # 미리보기 — 아무것도 안 씀
    assert "CONFIRM=1" in capsys.readouterr().out
    monkeypatch.setenv("CONFIRM", "1")
    assert ld.main(["x", "juhwan.kim@gmail.com", "juhwan"]) == 0
    assert inserted == [("memberships", [{"tenant_id": "t-j", "user_id": "u1", "role": "owner"}])]


def test_other_salon_needs_multi(monkeypatch):
    inserted = _fake(monkeypatch, [{"tenant_id": "t-h"}])
    monkeypatch.setenv("CONFIRM", "1")
    monkeypatch.delenv("MULTI", raising=False)
    assert ld.main(["x", "juhwan.kim@gmail.com", "juhwan"]) == 1 and inserted == []          # 다른 실제 매장 — 막는다
    monkeypatch.setenv("MULTI", "1")
    assert ld.main(["x", "juhwan.kim@gmail.com", "juhwan"]) == 0 and len(inserted) == 1


def test_already_linked_and_missing_do_nothing(monkeypatch):
    inserted = _fake(monkeypatch, [{"tenant_id": "t-j"}])
    monkeypatch.setenv("CONFIRM", "1")
    assert ld.main(["x", "juhwan.kim@gmail.com", "juhwan"]) == 0                               # 이미 — 할 일 없음
    assert ld.main(["x", "nobody@x.com", "juhwan"]) == 1
    assert ld.main(["x", "juhwan.kim@gmail.com", "nope"]) == 1
    assert inserted == []


def test_list_masks_emails(monkeypatch):
    lines = ld.list_lines(USERS, TENANTS, [
        {"tenant_id": "t-h", "user_id": "u2"}, {"tenant_id": "t-h", "user_id": "u3"}, {"tenant_id": "t-demo", "user_id": "u1"},
    ])
    text = "\n".join(lines)
    assert "hayewoni@naver.com" not in text and "h***@n***.com(마지막 로그인 2026-10-15)" in text
    assert "o***@e***.com(로그인 기록 없음)" in text
    assert lines[-1].strip().startswith("demo-")                                              # 데모는 맨 아래
    assert "juhwan" in text and "이어진 계정 없음" in text
