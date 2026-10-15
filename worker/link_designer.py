"""디자이너 계정을 매장에 잇는다 — 맥에서, 서비스 키로(개선 계획 v13 P0). 미리보기가 기본.

순서
    1) 디자이너님이 앱 주소 끝에 /start 를 붙여 열고 안내대로 로그인한다
    2) '아직 매장에 연결되지 않았어요' 화면의 이메일을 운영자에게 알려 준다
    3) 운영자가 이것을 돌린다 — 미리보기로 확인하고, CONFIRM=1 로 다시

전에는 Supabase 에서 사용자 id 를 찾아 소속(memberships) SQL 을 손으로 썼다(소속을 만드는 코드는 데모뿐).
매장을 잘못 이으면 남의 손님이 보이므로, 이미 다른 실제 매장에 이어진 계정은 MULTI=1 없이는 잇지 않는다.
데모 매장 소속은 건드리지 않는다 — 앱이 실제 매장을 먼저 연다(web/lib/tenant-pick).
손님 정보는 읽지 않고, 이메일은 가려서만 찍는다.

사용:
    .venv/bin/python worker/link_designer.py 이메일 매장
    CONFIRM=1 .venv/bin/python worker/link_designer.py 이메일 매장
    .venv/bin/python worker/link_designer.py --list
"""

from __future__ import annotations

import os
import sys

from env import load_env

load_env()

DEMO_PREFIX = "demo-"  # web/lib/tenant-pick.ts 와 같은 이름표


def mask_email(email: str | None) -> str:
    """'juhwan.kim@gmail.com' → 'j***@g***.com' — 누구 것인지 운영자는 알아보고, 기록엔 남지 않게."""
    if not email or "@" not in email:
        return "(이메일 없음)"
    local, _, domain = email.partition("@")
    host, dot, tld = domain.rpartition(".")
    if not dot:
        host, tld = domain, ""
    return f"{local[:1]}***@{host[:1]}***" + (f".{tld}" if tld else "")


def decide(email: str, slug: str, users: list[dict], tenants: list[dict], memberships: list[dict]) -> dict:
    """무엇을 할지 — 네트워크 없이 판정한다(테스트가 이걸 본다).

    users = 계정(id · email), tenants = 매장(id · slug), memberships = 이 계정의 소속(tenant_id).
    action: link(이어도 됨) · already(이미 이어짐) · no_user · no_tenant · other_salon(다른 실제 매장에 이미 — MULTI=1 필요)
    """
    want = email.strip().lower()
    user = next((u for u in users if (u.get("email") or "").strip().lower() == want), None)
    tenant = next((t for t in tenants if t.get("slug") == slug), None)
    if not user:
        return {"action": "no_user", "message": f"{mask_email(email)} 계정이 없어요 — 디자이너님께 먼저 앱 주소/start 로 로그인해 달라고 하세요"}
    if not tenant:
        known = ", ".join(sorted(t["slug"] for t in tenants if t.get("slug") and not t["slug"].startswith(DEMO_PREFIX)))
        return {"action": "no_tenant", "message": f"'{slug}' 매장이 없어요 — 있는 매장: {known or '(없음)'}"}
    by_id = {t["id"]: t.get("slug") or "?" for t in tenants}
    mine = [m["tenant_id"] for m in memberships]
    base = {"user_id": user["id"], "tenant_id": tenant["id"], "who": mask_email(user.get("email"))}
    if tenant["id"] in mine:
        return {**base, "action": "already", "message": f"{base['who']} 은 이미 '{slug}' 매장에 이어져 있어요 — 할 일 없음"}
    others = [by_id.get(t, "?") for t in mine if not str(by_id.get(t, "")).startswith(DEMO_PREFIX)]
    if others:
        return {**base, "action": "other_salon", "others": others,
                "message": (f"{base['who']} 은 이미 다른 실제 매장({', '.join(others)})에 이어져 있어요 — 매장이 둘이면 먼저 이은 "
                            f"매장이 열려요. 정말 '{slug}' 도 이으려면 MULTI=1 을 붙이세요")}
    demo = [by_id.get(t, "?") for t in mine if str(by_id.get(t, "")).startswith(DEMO_PREFIX)]
    note = " (데모 매장 소속은 그대로 — 앱은 실제 매장을 먼저 연다)" if demo else ""
    return {**base, "action": "link", "message": f"{base['who']} → '{slug}' 매장에 잇습니다{note}"}


def _users() -> list[dict]:
    """계정 전부(id · email · 마지막 로그인) — 인증 관리 API(서비스 키). 사용 현황 점검(usage_probe)과 같은 길."""
    import httpx
    import supa

    base = supa._base().removesuffix("/rest/v1")
    out: list[dict] = []
    with httpx.Client(timeout=30) as c:
        page = 1
        while True:
            r = c.get(f"{base}/auth/v1/admin/users", params={"page": page, "per_page": 200}, headers=supa._headers())
            supa._check(r)
            users = r.json().get("users") or []
            out += [{"id": u["id"], "email": u.get("email"), "last_sign_in_at": u.get("last_sign_in_at")} for u in users]
            if len(users) < 200:
                return out
            page += 1


def _tenants() -> list[dict]:
    import supa

    return supa._get("/tenants", {"select": "id,slug", "order": "slug"})


def _memberships(user_id: str | None = None) -> list[dict]:
    import supa

    params = {"select": "tenant_id,user_id,role"}
    if user_id:
        params["user_id"] = f"eq.{user_id}"
    return supa._get("/memberships", params)


def list_lines(users: list[dict], tenants: list[dict], memberships: list[dict]) -> list[str]:
    """매장마다 이어진 계정 — 이메일은 가려서, 마지막 로그인 날짜만."""
    by_user = {u["id"]: u for u in users}
    lines = []
    for t in sorted(tenants, key=lambda t: (str(t.get("slug") or "").startswith(DEMO_PREFIX), t.get("slug") or "")):
        ms = [m for m in memberships if m["tenant_id"] == t["id"]]
        who = []
        for m in ms:
            u = by_user.get(m["user_id"], {})
            seen = (u.get("last_sign_in_at") or "")[:10]
            who.append(f"{mask_email(u.get('email'))}(" + (f"마지막 로그인 {seen}" if seen else "로그인 기록 없음") + ")")
        lines.append(f"  {t.get('slug') or '?':14s} " + (" · ".join(who) if who else "이어진 계정 없음"))
    return lines


def main(argv: list[str]) -> int:
    if argv[1:] == ["--list"]:
        print("매장마다 이어진 계정 — 이메일은 가려서\n")
        print("\n".join(list_lines(_users(), _tenants(), _memberships())))
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    email, slug = argv[1], argv[2]
    users = _users()
    user = next((u for u in users if (u.get("email") or "").strip().lower() == email.strip().lower()), None)
    plan = decide(email, slug, users, _tenants(), _memberships(user["id"]) if user else [])
    print(plan["message"])
    if plan["action"] not in ("link", "other_salon"):
        return 0 if plan["action"] == "already" else 1
    if plan["action"] == "other_salon" and not os.environ.get("MULTI"):
        return 1
    if not os.environ.get("CONFIRM"):
        print("미리보기예요 — 이으려면 앞에 CONFIRM=1 을 붙여 다시 실행하세요")
        return 0
    import supa

    supa.insert("memberships", [{"tenant_id": plan["tenant_id"], "user_id": plan["user_id"], "role": "owner"}])
    print("이었어요 — 디자이너님께 앱에서 '다시 확인'을 눌러 달라고 하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
