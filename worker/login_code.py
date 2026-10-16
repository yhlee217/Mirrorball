"""새 디자이너 첫 로그인 — 맥에서, 서비스 키로(개선 계획 v15 P0). 미리보기가 기본.

앱 로그인은 메일로 온 6자리 코드를 앱에 넣는 방식이다. 그런데 메일 설정(SMTP)을 따로 하지 않았다면 Supabase 기본
메일은 프로젝트 팀원 주소로만 · 한 시간에 2통 보내고, 기본 메일 양식엔 코드가 없다(링크만). 그래서 디자이너님께
코드가 안 갈 수 있다 — 이 스크립트가 메일 없이 코드를 바로 만든다.

하는 일
    1) 계정이 없으면 만든다(메일 확인된 상태로 — 디자이너님이 메일을 열 일이 없다)
    2) 매장을 주면 잇는다 — link_designer 와 같은 규칙(데모 소속은 그대로, 다른 실제 매장은 MULTI=1)
    3) 앱 로그인 코드(6자리)를 화면에만 찍는다 — 파일 · 운영 기록 어디에도 남기지 않는다

디자이너님은 홈 화면 앱의 로그인 화면에서 이메일 → '코드를 이미 받았다면 입력하기' → 코드. 매장을 미리 이어 두면
바로 자기 매장이 열린다. 코드는 한 번만 · 1시간 안에(Supabase 설정값), 새로 만들면 앞의 코드는 못 쓴다.
코드는 전화나 카톡으로 불러 준다.

사용:
    .venv/bin/python worker/login_code.py 이메일 매장
    CONFIRM=1 .venv/bin/python worker/login_code.py 이메일 매장
    CONFIRM=1 .venv/bin/python worker/login_code.py 이메일          # 이미 이어진 계정 — 코드만
"""

from __future__ import annotations

import os
import re
import sys

from env import load_env

load_env()

import link_designer as ld  # noqa: E402

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def plan(email: str, slug: str | None, users: list[dict], tenants: list[dict], memberships: list[dict]) -> dict:
    """무엇을 할지 — 네트워크 없이 판정한다(테스트가 이걸 본다).

    create(계정 만들기) · link(매장 잇기) · blocked(멈춤 — 이유는 message), steps 는 화면에 찍을 줄들(이메일은 가려서).
    """
    want = email.strip().lower()
    who = ld.mask_email(want)
    if not EMAIL.match(want):
        return {"blocked": True, "message": f"이메일 모양이 아니에요: {who}"}
    user = next((u for u in users if (u.get("email") or "").strip().lower() == want), None)
    steps = [] if user else [f"{who} 계정이 없어요 — 만듭니다(메일 확인된 상태로)"]
    out = {"blocked": False, "create": user is None, "link": False, "user_id": user["id"] if user else None,
           "tenant_id": None, "who": who}
    if slug:
        if user:
            d = ld.decide(want, slug, users, tenants, memberships)
        else:   # 새 계정은 소속이 없다 — 있는 계정처럼 판정하되 아이디만 비워 둔다
            d = ld.decide(want, slug, [{"id": "", "email": want}], tenants, [])
        if d["action"] == "no_tenant":
            return {"blocked": True, "message": d["message"]}
        if d["action"] == "other_salon" and not os.environ.get("MULTI"):
            return {"blocked": True, "message": d["message"]}
        out["tenant_id"] = d.get("tenant_id")
        out["link"] = d["action"] in ("link", "other_salon")
        steps.append(d["message"])
    steps.append(f"{who} 의 앱 로그인 코드를 만듭니다(메일은 보내지 않아요)")
    return {**out, "steps": steps}


def otp_of(resp: dict) -> str | None:
    """generate_link 응답에서 6자리 코드 — 사용자 항목과 같은 층에 오고(email_otp), 라이브러리를 거치면 properties 안."""
    if not isinstance(resp, dict):
        return None
    code = resp.get("email_otp") or (resp.get("properties") or {}).get("email_otp")
    return str(code) if code else None


def _auth_base() -> str:
    import supa

    return supa._base().removesuffix("/rest/v1") + "/auth/v1"


def _create_user(email: str) -> str:
    import httpx
    import supa

    with httpx.Client(timeout=30) as c:
        r = c.post(f"{_auth_base()}/admin/users", json={"email": email, "email_confirm": True}, headers=supa._headers())
        supa._check(r)
        return r.json()["id"]


def _login_code(email: str) -> str:
    import httpx
    import supa

    with httpx.Client(timeout=30) as c:
        r = c.post(f"{_auth_base()}/admin/generate_link", json={"type": "magiclink", "email": email},
                   headers=supa._headers())
        supa._check(r)
        code = otp_of(r.json())
    if not code:
        raise RuntimeError("코드를 받지 못했어요 — Supabase 응답에 email_otp 가 없다")
    return code


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    email, slug = argv[1].strip(), (argv[2].strip() if len(argv) == 3 else None)
    users = ld._users()
    user = next((u for u in users if (u.get("email") or "").strip().lower() == email.lower()), None)
    p = plan(email, slug, users, ld._tenants() if slug else [], ld._memberships(user["id"]) if user and slug else [])
    if p["blocked"]:
        print(p["message"])
        return 1
    print("\n".join(p["steps"]))
    if not os.environ.get("CONFIRM"):
        print("미리보기예요 — 하려면 앞에 CONFIRM=1 을 붙여 다시 실행하세요")
        return 0
    user_id = p["user_id"] or _create_user(email.lower())
    if p["link"]:
        import supa

        supa.insert("memberships", [{"tenant_id": p["tenant_id"], "user_id": user_id, "role": "owner"}])
    code = _login_code(email.lower())
    print(f"\n로그인 코드  {code}")
    print(f"  · 디자이너님 앱 로그인 화면 → 이메일 {p['who']} → '코드를 이미 받았다면 입력하기' → 이 코드")
    print("  · 한 번만 · 1시간 안에(Supabase 설정값). 새로 만들면 앞의 코드는 못 써요. 전화나 카톡으로 불러 주세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
