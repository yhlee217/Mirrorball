"""사용 현황 — 디자이너가 앱을 실제로 쓰고 있나(개선 계획 v5 P4). 읽기 전용, 숫자만.

다음 기능(내 말투로 등)을 감으로 정하지 않으려고 잰다. 디자이너별:
  · 마지막 접속일 — Supabase 로그인 기록(auth)
  · 연락 수 — 챙길 고객에서 문자 · 전화 · 공유(카톡 등) · 복사를 한 손님 수(지난 1주 / 4주), 수단별
  · 이탈 표시 — 지난 4주에 직접 '이탈 처리'한 손님 수
이메일·이름·전화는 찍지 않는다(매장 slug 와 날짜·건수만).

사용:
    .venv/bin/python worker/usage_probe.py
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from env import load_env

load_env()

KST = dt.timezone(dt.timedelta(hours=9))


def _when(iso: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def measure(members: list[dict], last_sign_in: dict[str, str | None], contacts: list[dict],
            customers: list[dict], now: dt.datetime) -> dict:
    """한 매장. members = 이 매장 멤버십(user_id), last_sign_in = user_id → 마지막 로그인(ISO)."""
    seen = [w for w in (_when(last_sign_in.get(m["user_id"])) for m in members) if w]
    week, month = now - dt.timedelta(days=7), now - dt.timedelta(days=28)

    def people(since: dt.datetime) -> tuple[int, Counter]:
        rows = [c for c in contacts if c.get("customer_id") and (_when(c.get("sent_at")) or now) >= since]
        return len({c["customer_id"] for c in rows}), Counter(c.get("why") or "?" for c in rows)

    w_n, _ = people(week)
    m_n, m_via = people(month)
    churned = sum(1 for c in customers if (_when(c.get("churned_at")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)) >= month)
    return {
        "users": len(members),
        "last_seen": max(seen) if seen else None,
        "contacted_7": w_n,
        "contacted_28": m_n,
        "via_28": dict(m_via),
        "churned_28": churned,
    }


def report(slug: str, m: dict, now: dt.datetime) -> str:
    last = m["last_seen"]
    seen = "접속 기록 없음" if not last else (
        f"마지막 접속 {last.astimezone(KST):%m.%d} ({(now - last).days}일 전)")
    via = " · ".join(f"{ {'sms': '문자', 'call': '전화', 'copy': '복사', 'share': '공유'}.get(k, k)} {v}"
                     for k, v in sorted(m["via_28"].items()))
    return (f"[{slug}] 계정 {m['users']}개 · {seen} · 연락 지난 1주 {m['contacted_7']}명 · 4주 {m['contacted_28']}명"
            + (f"({via})" if via else "") + f" · 이탈 처리 4주 {m['churned_28']}명")


def verdict(ms: dict[str, dict], now: dt.datetime) -> list[str]:
    out = []
    quiet = [s for s, m in ms.items() if not m["last_seen"] or (now - m["last_seen"]).days >= 7]
    if quiet:
        out.append(f"한 주 넘게 접속이 없는 곳: {', '.join(quiet)} — 쓰기 어려운 점을 직접 물어볼 때")
    idle = [s for s, m in ms.items() if m["contacted_28"] == 0 and s not in quiet]
    if idle:
        out.append(f"접속은 하지만 4주간 연락이 없는 곳: {', '.join(idle)} — 챙길 고객 문구·흐름을 다시 볼 때")
    if not out:
        out.append("모두 한 주 안에 접속했고 연락 기록이 있다 — '내 말투로'(v4 P3)를 판단할 만큼 쓰이고 있다")
    return out


def _auth_users() -> dict[str, str | None]:
    """user_id → 마지막 로그인. 서비스 키로 Supabase 인증 관리 API 를 읽는다(이메일은 쓰지 않는다)."""
    import httpx
    import supa

    base = supa._base().removesuffix("/rest/v1")
    out: dict[str, str | None] = {}
    page = 1
    with httpx.Client(timeout=30) as c:
        while True:
            r = c.get(f"{base}/auth/v1/admin/users", params={"page": page, "per_page": 200}, headers=supa._headers())
            supa._check(r)
            users = r.json().get("users") or []
            for u in users:
                out[u["id"]] = u.get("last_sign_in_at")
            if len(users) < 200:
                return out
            page += 1


def main() -> int:
    import supa

    now = dt.datetime.now(dt.timezone.utc)
    signs = _auth_users()
    print(f"사용 현황 · {now.astimezone(KST):%Y-%m-%d %H:%M} KST · 읽기 전용(날짜·건수만)\n")
    ms: dict[str, dict] = {}
    since = (now - dt.timedelta(days=28)).isoformat()
    for t in supa._get("/tenants", {"select": "id,slug", "order": "slug"}):
        q = {"tenant_id": f"eq.{t['id']}"}
        members = supa._get("/memberships", {**q, "select": "user_id"})
        if not members:
            continue  # 수집용 살롱 테넌트처럼 사람이 들어오지 않는 곳
        contacts = supa._get("/care_items", {**q, "kind": "eq.contact", "sent_at": f"gte.{since}",
                                             "select": "customer_id,why,sent_at"})
        churned = supa._get("/customers", {**q, "churned_at": f"gte.{since}", "select": "churned_at"})
        m = measure(members, signs, contacts, churned, now)
        ms[t.get("slug") or t["id"][:8]] = m
        print(report(t.get("slug") or t["id"][:8], m, now))
    print("\n판단\n")
    print("\n".join("  " + v for v in verdict(ms, now)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
