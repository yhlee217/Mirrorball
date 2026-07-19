#!/usr/bin/env python3
"""예약 수집 진단 — reserveList 를 실제로 열어 '어디서 행이 사라지는지' 단계별로 센다.

맥에서:  .venv/bin/python worker/probe_reserve.py
HTML 은 _raw/reserve/page.html 로 저장(구조 확인용). Supabase 는 건드리지 않는다.

단계: 로드된 행 → RESERVE 링크 필터 → 파싱 성공 → 예약중 → 오늘 이후 → 담당별
여기서 뚝 떨어지는 지점이 곧 원인이다(페이지네이션 미로드 / 파서 누락 / 필터 과다).
"""
from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

RESERVE_URL = "https://www1.handsos.com/work/reserve/reserveList.asp"
LOGIN_URL = "https://www.handsos.com/login/login.asp?p=pc"
HOME_URL = "https://www1.handsos.com/work/default.asp"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
DAYS_AHEAD = 31


def _creds():
    import yaml
    s = (yaml.safe_load((ROOT / "secrets" / "stores.yaml").read_text(encoding="utf-8")) or {}).get("stores") or [{}]
    s = s[0]
    return str(s.get("company_code") or ""), str(s.get("username") or ""), str(s.get("password") or "")


def main() -> int:
    from playwright.sync_api import sync_playwright
    import handsos_reserve as hr

    company, uid, pw = _creds()
    start, end = str(date.today()), str(date.today() + timedelta(days=DAYS_AHEAD))
    outdir = ROOT / "_raw" / "reserve"
    outdir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())
        page.set_default_timeout(30000)
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.fill("#companyID", company); page.fill("#userID", uid); page.fill("#userPWD", pw)
            page.click("#sendLogin")
            page.wait_for_load_state("networkidle")
            if page.is_visible("#userPWD"):
                print("login-failed"); return 1

            page.goto(HOME_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            page.evaluate(
                "a=>{var f=document.querySelector('frame[name=\"'+a.n+'\"],iframe[name=\"'+a.n+'\"],#'+a.n);"
                "if(f){f.src=a.u;}}", {"n": "mainFrame", "u": RESERVE_URL})
            fr = None
            for _ in range(24):
                page.wait_for_timeout(500)
                fr = next((f for f in page.frames if "reserveList" in (f.url or "")), None)
                if fr:
                    break
            if not fr:
                print("no-reserve-frame"); return 1

            for sel, val in (("#strDateS", start), ("#strDateE", end)):
                try:
                    fr.fill(sel, val)
                except Exception:
                    pass
            print(f"기간 {start} ~ {end} (+{DAYS_AHEAD}일)")

            # 전체보기 = DBProc(65000). 큰 결과는 로딩이 느릴 수 있어 넉넉히 기다린다.
            try:
                fr.evaluate("DBProc(65000)")
            except Exception as e:
                print("DBProc 실패:", e)
                try:
                    fr.click("a.icogSearch", timeout=4000)
                except Exception:
                    pass
            page.wait_for_timeout(6000)

            html = fr.content()
            (outdir / "page.html").write_text(f"<!-- {fr.url} -->\n" + html, encoding="utf-8")

            # 단계별 카운트
            trs = re.findall(r"<tr\b.*?</tr>", html, re.S)
            def txt(x): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()
            when = re.compile(r"\d{2}-\d{1,2}-\d{1,2}\D+?\d{1,2}:\d{2}")
            rows_time = [t for t in trs if when.search(txt(t))]
            rows_reserve = [t for t in rows_time if "strHowCateg=RESERVE" in t]
            parsed = [p for p in (hr.parse_row(c) for c in hr.extract_rows(html)) if p]
            today = str(date.today())
            booking = [r for r in parsed if r.get("status") and "예약중" in r["status"]]
            future = [r for r in booking if r["date"] >= today]

            print(f"\n[단계별 행 수]")
            print(f"  1) 예약시각 있는 행          : {len(rows_time)}")
            print(f"  2) RESERVE 링크 있는 행      : {len(rows_reserve)}   ← 파서가 취하는 대상")
            print(f"  3) 파싱 성공                 : {len(parsed)}")
            print(f"  4) 상태 '예약중'             : {len(booking)}")
            print(f"  5) 오늘 이후                 : {len(future)}   ← 앱에 들어갈 후보")

            from collections import Counter
            byst = Counter((r.get("staff") or "?") for r in future)
            print(f"\n[담당별 (오늘 이후·예약중)]")
            for s, n in byst.most_common():
                print(f"  {s:12s} {n}건")
            print(f"\n[상태 분포(전체 파싱분)]")
            for s, n in Counter((r.get("status") or "?") for r in parsed).most_common():
                print(f"  {s:12s} {n}건")
            print(f"\nHTML 저장: _raw/reserve/page.html")
            return 0
        except Exception as exc:
            print("예외:", str(exc).splitlines()[0][:200]); return 1
        finally:
            ctx.close(); b.close()


if __name__ == "__main__":
    raise SystemExit(main())
