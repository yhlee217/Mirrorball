#!/usr/bin/env python3
"""핸드SOS 매출상세목록 반자동 수집 — 로그인은 사람이, 표 수집만 자동.

원장님 Mac 에서 실행. 자격증명을 저장하지 않으므로(직접 로그인) 가장 안전하고 2FA 도 통과.

흐름:
  1) 브라우저가 열리면 — 직접 핸드SOS 로그인 → 매출분석 > 매출상세목록 →
     기간을 전체로 설정 → '검색' → 표(1페이지)가 보이게 한다.
  2) 터미널로 돌아와 Enter.
  3) 스크립트가 모든 페이지를 넘기며 표를 긁어 CSV 로 저장(중복 제거).
  4) python import_handsos.py 그CSV --slug hayewoni --staff 하예원

주의: 핸드SOS UI 변경 시 페이지 넘김이 안 될 수 있음 → 그땐 화면/오류를 공유하면 셀렉터 보정.
사전: pip install playwright  (브라우저는 한 번 'playwright install chromium')
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

# 데이터 표(매출상세목록) 행 추출 — '고객명'·'날짜' 헤더를 가진 표를 찾아 전 셀 텍스트로.
_EXTRACT_JS = r"""
() => {
  const tables = [...document.querySelectorAll('table')];
  const t = tables.find(tb => /고객명/.test(tb.innerText) && /날짜/.test(tb.innerText));
  if (!t) return null;
  return [...t.querySelectorAll('tr')].map(tr =>
    [...tr.querySelectorAll('th,td')].map(td => (td.innerText || '').replace(/\s+/g,' ').trim())
  );
}
"""

# 페이지 번호/다음(›,>) 을 정확한 텍스트로 클릭.
_CLICK_TEXT_JS = r"""
(target) => {
  const els = [...document.querySelectorAll('a,button,li,span,div')];
  const el = els.find(e => e.textContent.trim() === target && e.offsetParent !== null
                           && (e.onclick || e.tagName==='A' || e.tagName==='BUTTON' || e.closest('a,button,li')));
  if (el) { (el.closest('a,button,li') || el).click(); return true; }
  return false;
}
"""


def _total(page) -> int:
    try:
        txt = page.inner_text("body")
    except Exception:
        return 0
    m = re.search(r"총\s*([\d,]+)\s*개", txt)
    return int(m.group(1).replace(",", "")) if m else 0


def _is_data_row(cells: list[str]) -> bool:
    # 날짜 비슷한 첫 셀(YY-MM-DD 또는 YYYY-MM-DD)이 있으면 데이터 행
    return bool(cells) and bool(re.search(r"\d{2,4}\D\d{1,2}\D\d{1,2}", cells[0] or ""))


def harvest(page, max_pages: int, perpage: int) -> tuple[list[str], list[list[str]]]:
    header: list[str] = []
    seen: set[tuple] = set()
    rows: list[list[str]] = []
    total = _total(page)
    cap = max_pages or (total // max(perpage, 1) + 5 if total else 200)

    for pageno in range(1, cap + 1):
        table = page.evaluate(_EXTRACT_JS)
        if not table:
            print("  [!] '고객명/날짜' 표를 못 찾음 — 매출상세목록이 화면에 보이는지 확인")
            break
        if not header:
            header = next((r for r in table if "고객명" in r), table[0])
        before = len(seen)
        for r in table:
            if _is_data_row(r):
                key = tuple(r)
                if key not in seen:
                    seen.add(key)
                    rows.append(r)
        gained = len(seen) - before
        print(f"  · {pageno}p: 누적 {len(rows)}건" + (f" / 총 {total}" if total else ""))

        if total and len(rows) >= total:
            break
        # 다음 페이지로
        nxt = str(pageno + 1)
        moved = page.evaluate(_CLICK_TEXT_JS, nxt)
        if not moved:                                  # 블록 끝 → '›'/'>'/'다음'
            for arrow in ("›", "▶", ">", "다음", "Next"):
                if page.evaluate(_CLICK_TEXT_JS, arrow):
                    moved = True
                    break
        if not moved:
            print("  (다음 페이지 컨트롤 없음 — 마지막으로 간주)")
            break
        time.sleep(0.8)                                # 표 갱신 대기
        if gained == 0 and pageno > 1:                 # 더 안 늘면 종료
            break
    return header, rows


def run(out: str, max_pages: int, perpage: int, headless: bool) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            page.goto("https://s.handsos.com", wait_until="domcontentloaded")
        except Exception:
            page.goto("about:blank")
        print("\n" + "=" * 60)
        print("브라우저에서: 핸드SOS 로그인 → 매출분석 > 매출상세목록 →")
        print("기간을 전체로 설정 → '검색' → 표(1페이지)가 보이게 하세요.")
        print("준비되면 이 터미널에서 Enter ▶", end=" ")
        input()
        header, rows = harvest(page, max_pages, perpage)
        browser.close()

    if not rows:
        print("✗ 수집된 행이 없습니다. 표가 화면에 보였는지/페이징을 확인하세요.")
        return 1
    Path(out).write_text("", encoding="utf-8")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if header:
            w.writerow(header)
        w.writerows(rows)
    print(f"\n✓ {out}  ({len(rows)}건 저장)")
    print(f"  다음: python import_handsos.py {out} --slug hayewoni --staff 하예원")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 매출상세목록 반자동 수집")
    ap.add_argument("--out", default="handsos_매출상세.csv")
    ap.add_argument("--max-pages", type=int, default=0, help="0=자동(총건수 기반)")
    ap.add_argument("--perpage", type=int, default=20)
    ap.add_argument("--headless", action="store_true", help="디버그용(보통은 화면 보면서)")
    args = ap.parse_args()
    return run(args.out, args.max_pages, args.perpage, args.headless)


if __name__ == "__main__":
    raise SystemExit(main())
