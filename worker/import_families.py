#!/usr/bin/env python3
"""가족고객 현황(c_Family.asp) 수집 → customers.family_ext_id 갱신(전 테넌트).

가족 관계는 정적이라 매 수집(10분)마다 돌리지 않고, 필요 시/가끔만 실행한다.
맥에서:  .venv/bin/python worker/import_families.py
로그인은 secrets/stores.yaml(첫 store), DB 는 web/.env.local(SUPABASE_SERVICE_ROLE_KEY) 사용.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))  # worker/ (supa, handsos_family)


def _load_env() -> None:
    p = ROOT / "web" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]


_load_env()

import handsos_family as hf  # noqa: E402
import supa  # noqa: E402

FAMILY_URL = "https://www1.handsos.com/work/sale/cust/c_Family.asp"
LOGIN_URL = "https://www.handsos.com/login/login.asp?p=pc"
HOME_URL = "https://www1.handsos.com/work/default.asp"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _creds() -> tuple[str, str, str]:
    import yaml
    stores = (yaml.safe_load((ROOT / "secrets" / "stores.yaml").read_text(encoding="utf-8")) or {}).get("stores") or [{}]
    s = stores[0]
    return str(s.get("company_code") or ""), str(s.get("username") or ""), str(s.get("password") or "")


def harvest_family_htmls() -> list[str]:
    """c_Family.asp?page=n 을 1부터 끝까지 로드 → 각 페이지 HTML 리스트."""
    from playwright.sync_api import sync_playwright
    company, uid, pw = _creds()
    if not (company and uid and pw):
        raise RuntimeError("secrets/stores.yaml 자격증명 누락")
    htmls: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())
        page.set_default_timeout(30000)
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.fill("#companyID", company)
            page.fill("#userID", uid)
            page.fill("#userPWD", pw)
            page.click("#sendLogin")
            page.wait_for_load_state("networkidle")
            if page.is_visible("#userPWD"):
                raise RuntimeError("login-failed")
            page.goto(HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            prev = ""
            for n in range(1, 60):
                page.evaluate(
                    "a=>{var f=document.querySelector('#'+a.n+',frame[name=\"'+a.n+'\"],iframe[name=\"'+a.n+'\"]');"
                    "if(f){f.src=a.u;}}", {"n": "mainFrame", "u": f"{FAMILY_URL}?page={n}"})
                fr = None
                for _ in range(24):
                    page.wait_for_timeout(400)
                    fr = next((f for f in page.frames if "c_Family" in (f.url or "")), None)
                    if fr:
                        break
                if not fr:
                    break
                page.wait_for_timeout(700)
                h = fr.content()
                if not re.search(r"\d{7}", h) or h == prev:  # 고객번호 없음 or 이전과 동일(끝/클램프)
                    break
                htmls.append(h)
                prev = h
            return htmls
        finally:
            ctx.close()
            b.close()


def main() -> int:
    htmls = harvest_family_htmls()
    mp = hf.parse_families(htmls)
    print(f"수집 {len(htmls)}페이지, 매핑 {len(mp)}명")
    if not mp:
        print("매핑 0 — 중단(구조 변동 의심)")
        return 1
    tenants = supa._get("/tenants", {"select": "id,slug"})
    total = 0
    for t in tenants:
        tid = t["id"]
        custs = supa.select_all("customers", tid, "id,ext_id")
        upd = [{"id": c["id"], "tenant_id": tid, "family_ext_id": mp[c["ext_id"]]}
               for c in custs if c.get("ext_id") in mp]
        for i in range(0, len(upd), 500):
            supa.upsert("customers", upd[i:i + 500], "id")
        print(f"  {t['slug']}: {len(upd)}명 family_ext_id 갱신")
        total += len(upd)
    print("완료:", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
