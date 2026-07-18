#!/usr/bin/env python3
"""가족고객 현황(c_Family.asp) 전 페이지 HTML 덤프 → _raw/family/page{n}.html.

구조 파악용(파서 작성 전 1회). 맥에서:  .venv/bin/python worker/probe_family.py
로그인 자격증명은 secrets/stores.yaml(첫 store: company_code/username/password) 사용.
페이지네이션은 여러 방식(goPage(n) / ?page=n / 링크 클릭)을 시도해 최대한 다 덤프한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FAMILY_URL = "https://www1.handsos.com/work/sale/cust/c_Family.asp"
LOGIN_URL = "https://www.handsos.com/login/login.asp?p=pc"
HOME_URL = "https://www1.handsos.com/work/default.asp"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _creds() -> dict:
    import yaml
    data = yaml.safe_load((ROOT / "secrets" / "stores.yaml").read_text(encoding="utf-8")) or {}
    s = (data.get("stores") or [{}])[0]
    return {"company": str(s.get("company_code") or ""), "id": str(s.get("username") or ""),
            "pw": str(s.get("password") or "")}


def _get_frame(page, needle: str):
    for _ in range(24):
        page.wait_for_timeout(500)
        fr = next((f for f in page.frames if needle in (f.url or "")), None)
        if fr:
            return fr
    return None


def main() -> int:
    from playwright.sync_api import sync_playwright
    c = _creds()
    if not (c["company"] and c["id"] and c["pw"]):
        print("secrets/stores.yaml 자격증명 누락"); return 1
    outdir = ROOT / "_raw" / "family"
    outdir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())
        page.set_default_timeout(30000)
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.fill("#companyID", c["company"]); page.fill("#userID", c["id"]); page.fill("#userPWD", c["pw"])
            page.click("#sendLogin")
            page.wait_for_load_state("networkidle")
            if page.is_visible("#userPWD"):
                print("login-failed"); return 1

            page.goto(HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            page.evaluate(
                "a=>{var f=document.querySelector('frame[name=\"'+a.n+'\"],iframe[name=\"'+a.n+'\"],#'+a.n);"
                "if(f){f.src=a.u;}}", {"n": "mainFrame", "u": FAMILY_URL})
            fr = _get_frame(page, "c_Family")
            if not fr:
                print("no-family-frame"); return 1
            page.wait_for_timeout(1500)

            (outdir / "page1.html").write_text(f"<!-- {fr.url} -->\n" + fr.content(), encoding="utf-8")
            rows1 = len(re.findall(r"01\d[-\s]?\d{3,4}[-\s]?\d{4}", fr.content()))
            print(f"page1 저장 (전화패턴 {rows1}개)")

            # 페이지네이션 힌트 덤프 — 숫자 링크의 onclick/href
            hints = fr.evaluate(
                "()=>JSON.stringify([...document.querySelectorAll('a')]"
                ".map(x=>({t:(x.textContent||'').trim(),h:x.getAttribute('href')||'',c:x.getAttribute('onclick')||''}))"
                ".filter(x=>/^(\\d+|다음|끝|전체보기)$/.test(x.t)||/page|goPage|Family/i.test(x.h+x.c)))")
            (outdir / "pagination_hints.json").write_text(hints, encoding="utf-8")
            print("페이지네이션 힌트:", hints[:800])

            # 2~12페이지 best-effort: goPage(n) → ?page=n 순으로 시도, 내용 바뀌면 저장
            prev = fr.content()
            for n in range(2, 13):
                got = False
                for attempt in (lambda: fr.evaluate(f"try{{goPage({n})}}catch(e){{}}"),
                                lambda: page.evaluate(
                                    "a=>{var f=document.querySelector('#'+a.n+',frame[name=\"'+a.n+'\"],iframe[name=\"'+a.n+'\"]');if(f){f.src=a.u;}}",
                                    {"n": "mainFrame", "u": f"{FAMILY_URL}?page={n}"})):
                    try:
                        attempt()
                        page.wait_for_timeout(1800)
                        fr2 = _get_frame(page, "c_Family") or fr
                        html = fr2.content()
                        if html and html != prev and re.search(r"01\d[-\s]?\d{3,4}", html):
                            (outdir / f"page{n}.html").write_text(f"<!-- {fr2.url} -->\n" + html, encoding="utf-8")
                            print(f"page{n} 저장")
                            prev = html; fr = fr2; got = True
                            break
                    except Exception:
                        continue
                if not got:
                    print(f"page{n} 없음(끝) — 중단"); break
            print("완료: _raw/family/ 확인")
            return 0
        except Exception as exc:
            print("예외:", str(exc).splitlines()[0][:200]); return 1
        finally:
            ctx.close(); b.close()


if __name__ == "__main__":
    raise SystemExit(main())
