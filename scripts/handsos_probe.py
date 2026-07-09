#!/usr/bin/env python3
"""핸드SOS 고객관리/고객상세 화면 '구조 진단' 도구 (생일 스크랩 준비용).

매출상세목록엔 생일 칼럼이 없어, 생일은 고객관리 화면에서 따로 긁어야 한다.
그 화면 구조(메뉴 경로·표 구조·생일 표기)를 모르니, 먼저 이 도구로 '한 번 열어
덤프' 해서 실제 DOM 을 확인 → 그에 맞춰 정식 수집기(handsos_customer_harvest)를 구현한다.
(페이지네이션 때 성공한 '진단 먼저' 방식 — 헛다리 방지)

하는 일:
  1) stores.yaml 자격증명으로 로그인(handsos_sync 의 검증된 로직 재사용)
  2) 홈 메뉴 링크를 모두 덤프 → '고객/회원/생일' 들어간 메뉴 후보를 콘솔에 출력
  3) (헤드리스 아님) 사용자가 브라우저에서 고객관리→고객상세로 직접 이동할 시간을 줌
  4) 열린 모든 프레임의 HTML·스크린샷을 _raw/{slug}/probe_*/ 에 저장 +
     '생일/생년월일/birth' 주변 텍스트 구간을 콘솔에 출력

사용:
  python scripts/handsos_probe.py --only hayewoni --headed         # 창 띄워 수동 이동
  python scripts/handsos_probe.py --only hayewoni --url <고객페이지URL>  # URL 직접 지정
  python scripts/handsos_probe.py --only hayewoni --headed --wait 30   # 이동 대기 30초

출력물(붙여넣어 주시면 정식 수집기를 정확히 맞춥니다):
  · 콘솔의 '고객 메뉴 후보' 목록과 '생일 주변 텍스트'
  · _raw/{slug}/probe_*/page*.html (필요 시)
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# ───────────────────────── 순수 헬퍼(브라우저 없이 테스트 가능) ─────────────────────────
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _text(html: str) -> str:
    """태그 제거 + 공백 정규화 — 컨텍스트 출력을 사람이 읽기 쉽게."""
    return _WS.sub(" ", _TAG.sub(" ", html or "")).strip()


# 메뉴 후보: 텍스트에 이 단어가 있으면 고객관리 진입점일 가능성
_MENU_HINT = re.compile(r"고객|회원|생일|생년|customer|member|birth", re.I)
_A_RE = re.compile(r"<a\b[^>]*>.*?</a>", re.I | re.S)
_HREF_RE = re.compile(r"""href\s*=\s*['"]([^'"]*)['"]""", re.I)
_ONCLICK_RE = re.compile(r"""onclick\s*=\s*['"]([^'"]*)['"]""", re.I)


def menu_links_from_html(html: str) -> list[dict]:
    """HTML 에서 링크(<a>)를 뽑아 {text, href, onclick} 리스트로. 고객 메뉴 탐색용.

    href='#', 빈 텍스트는 제외. 실제 클릭 대상(href/onclick)만 남긴다."""
    out = []
    for m in _A_RE.finditer(html or ""):
        chunk = m.group(0)
        text = _text(chunk)
        if not text:
            continue
        href = (_HREF_RE.search(chunk) or [None, ""])[1].strip()
        onclick = (_ONCLICK_RE.search(chunk) or [None, ""])[1].strip()
        if href in ("", "#") and not onclick:      # 실제 이동 대상 없는 장식 링크 제외
            continue
        out.append({"text": text, "href": href, "onclick": onclick})
    return out


def customer_menu_candidates(links: list[dict]) -> list[dict]:
    """메뉴 링크 중 '고객/회원/생일' 관련만 — 진입점 후보."""
    seen, out = set(), []
    for lk in links:
        blob = f"{lk['text']} {lk['href']} {lk['onclick']}"
        if not _MENU_HINT.search(blob):
            continue
        key = (lk["text"], lk["href"], lk["onclick"])
        if key in seen:
            continue
        seen.add(key)
        out.append(lk)
    return out


_BDAY_RE = re.compile(r"생일|생년월일|생년|birth", re.I)


def birthday_context(html: str, radius: int = 120) -> list[str]:
    """'생일/생년월일/birth' 가 나오는 지점 주변 텍스트 구간을 반환 — 표기·인접칼럼 확인용.

    태그를 지운 순수 텍스트에서 앵커 주변 radius 글자를 잘라 준다(중복 제거)."""
    txt = _text(html)
    out, seen = [], set()
    for m in _BDAY_RE.finditer(txt):
        s = max(0, m.start() - radius)
        e = min(len(txt), m.end() + radius)
        snippet = txt[s:e].strip()
        if snippet not in seen:
            seen.add(snippet)
            out.append(snippet)
    return out


def _print_findings(where: str, html: str) -> int:
    """한 프레임의 메뉴 후보·생일 컨텍스트를 콘솔에 요약. 발견 수 반환."""
    cands = customer_menu_candidates(menu_links_from_html(html))
    ctx = birthday_context(html)
    if cands:
        print(f"  [{where}] 고객 메뉴 후보 {len(cands)}개:")
        for c in cands[:20]:
            tgt = c["href"] or c["onclick"]
            print(f"     · {c['text']}  →  {tgt[:90]}")
    if ctx:
        print(f"  [{where}] '생일' 주변 텍스트 {len(ctx)}건:")
        for s in ctx[:12]:
            print(f"     · …{s}…")
    return len(cands) + len(ctx)


# ───────────────────────── Playwright 진단(브라우저) ─────────────────────────
def probe_store(store: dict, *, url: str | None, wait_s: int, headed: bool) -> int:
    """로그인 → (URL 또는 수동 이동) → 모든 프레임 HTML·스크린샷 저장 + 생일 앵커 출력."""
    from playwright.sync_api import sync_playwright

    import handsos_sync as hs
    hs.apply_overrides(store)
    login = {**hs.DEFAULT_LOGIN, **(store.get("login") or {})}
    fields = {**hs.DEFAULT_LOGIN["fields"], **(login.get("fields") or {})}
    slug = store["slug"]
    outdir = ROOT / "_raw" / slug / ("probe_" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    outdir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed,
                                     args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            user_agent=store.get("user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900})
        page = ctx.new_page()

        def _accept_dialog(d):
            try:
                d.accept()
            except Exception:
                pass
        page.on("dialog", _accept_dialog)
        page.set_default_timeout(int(store.get("timeout_ms", 30000)))
        try:
            # 1) 로그인
            page.goto(login["url"], wait_until="domcontentloaded")
            hs._fill(page, fields.get("company_code"), store.get("company_code", ""))
            hs._fill(page, fields.get("username"), store.get("username", ""))
            hs._fill(page, fields.get("password"), store.get("password", ""))
            if login.get("submit"):
                page.click(login["submit"])
            page.wait_for_load_state("networkidle")
            if page.is_visible(fields.get("password") or "#userPWD"):
                print("✗ 로그인 실패 — 자격증명 확인(회사코드/아이디/비번)")
                return 2
            print(f"✓ 로그인 성공: {slug}")

            # 2) 홈으로 이동(메뉴 덤프) → 고객관리 URL 지정 시 그 프레임 로드
            report = store.get("report") or {}
            home = report.get("home_url", "https://www1.handsos.com/work/default.asp")
            page.goto(home, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if url:
                fname = report.get("frame_name", "mainFrame")
                page.evaluate(
                    "a=>{var f=document.querySelector('frame[name=\"'+a.n+'\"],iframe[name=\"'+a.n+'\"],#'+a.n);"
                    "if(f){f.src=a.u;}}", {"n": fname, "u": url})
                print(f"  → 지정 URL 로드: {url}")

            # 3) 수동 이동 대기(헤드리스 아니면): 사장님이 고객관리→고객상세로 직접 이동
            if headed and wait_s > 0:
                print(f"‹진단› 브라우저에서 '고객관리 → 고객상세' 화면으로 이동해 주세요. "
                      f"{wait_s}초 후 자동으로 덤프합니다…")
            end = wait_s
            while end > 0:
                page.wait_for_timeout(1000)
                end -= 1

            # 4) 열린 모든 창/프레임 덤프 + 요약
            print("\n── 진단 결과 ──")
            found = 0
            fi = 0
            for pi, pg in enumerate(ctx.pages):
                try:
                    pg.screenshot(path=str(outdir / f"page{pi}.png"))
                except Exception:
                    pass
                for fr in pg.frames:
                    try:
                        html = fr.content()
                    except Exception:
                        continue
                    label = f"page{pi}"
                    if fr.url and "about:blank" not in fr.url:
                        label += f" · {fr.url.split('/')[-1] or fr.url}"
                    (outdir / f"frame{fi}.html").write_text(
                        f"<!-- {fr.url} -->\n{html}", encoding="utf-8")
                    fi += 1
                    found += _print_findings(label, html)
            print(f"\n저장: {outdir}  (프레임 {fi}개)")
            if not found:
                print("⚠ 고객 메뉴·생일 텍스트를 못 찾음 — 저장된 frame*.html 을 열어 확인하거나, "
                      "고객상세 화면까지 이동 후 --wait 를 늘려 재실행해 주세요.")
            else:
                print("↑ 위 '고객 메뉴 후보'/'생일 주변 텍스트'와 frame*.html 을 붙여넣어 주시면 "
                      "정식 생일 수집기를 정확히 맞추겠습니다.")
            return 0
        finally:
            ctx.close()
            browser.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 고객관리 화면 구조 진단(생일 스크랩 준비)")
    ap.add_argument("--stores", default=str(ROOT / "secrets" / "stores.yaml"))
    ap.add_argument("--only", help="이 slug 만(필수급)")
    ap.add_argument("--url", help="고객관리/고객상세 화면 URL 직접 지정(알면)")
    ap.add_argument("--wait", type=int, default=25, help="수동 이동 대기 초(기본 25)")
    ap.add_argument("--headed", action="store_true", help="브라우저 창 표시(수동 이동에 필요)")
    args = ap.parse_args()

    import handsos_sync as hs
    if not Path(args.stores).exists():
        print(f"✗ 설정 없음: {args.stores} — secrets/stores.example.yaml 복사해 채우세요.")
        return 2
    stores = hs.load_stores(args.stores)
    if args.only:
        stores = [s for s in stores if s["slug"] == args.only]
    if not stores:
        print("대상 매장 없음(--only 확인)")
        return 1
    store = stores[0]                      # 진단은 한 매장씩(로그인 1회)
    return probe_store(store, url=args.url, wait_s=args.wait, headed=args.headed)


if __name__ == "__main__":
    raise SystemExit(main())
