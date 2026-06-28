#!/usr/bin/env python3
"""발견 케어 측정기 — AI(Claude CLI) + 네이버(공개 검색 스크랩). 실행 환경에서만 동작.

- measure_ai: 질문을 Claude CLI(`claude -p`, 키 0)에 던지고 답변에서 디자이너/매장 언급 추출.
- measure_naver: search.naver.com 공개 검색을 스크랩해 노출/순위 추정(로그인 불필요).
  네이버 DOM 셀렉터는 바뀌므로, 안 잡히면 --debug 로 확인해 NAVER_PLACE_SEL 만 고친다.

substring 매칭으로 충분(NER 불필요). 측정 후 expose.build_exposure 가 점수·처방·추세를 만든다.
"""

from __future__ import annotations

import re
import subprocess
import urllib.parse

# 네이버 플레이스 결과 아이템 셀렉터(바뀌면 여기만 수정). 여러 후보를 순서대로 시도.
NAVER_PLACE_SEL = [
    "li.UEzoS", "li[class*='place']", "div.place_section li",
    "ul li a[href*='place']",
]
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
_COMP_RE = re.compile(r"[가-힣A-Za-z0-9]+(?:헤어|살롱|미용실|뷰티|바버|스튜디오)")


def _names(target: dict) -> list[str]:
    d = target.get("designer", {}) or {}
    s = target.get("salon", {}) or {}
    names = [d.get("name"), s.get("name")] + (d.get("aliases") or []) + (s.get("aliases") or [])
    return [n for n in names if n]


def _mentioned(text: str, names: list[str]) -> bool:
    return any(n and n in (text or "") for n in names)


def _competitors(text: str, names: list[str]) -> list[str]:
    out: list[str] = []
    for m in _COMP_RE.findall(text or ""):
        if m not in names and m not in out:
            out.append(m)
    return out[:5]


def _claude(prompt: str, timeout: int = 150) -> str:
    try:
        r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def measure_ai(target: dict) -> list[dict]:
    names = _names(target)
    qs: list[dict] = []
    for q in target.get("questions", []) or []:
        ans = _claude(q + "\n\n(한국 미용실/헤어 디자이너 추천. 실제로 알려진 곳만, 모르면 모른다고 말해줘.)")
        ment = _mentioned(ans, names)
        excerpt = ""
        if ment:
            for sent in re.split(r"(?<=[.!?\n])", ans):
                if _mentioned(sent, names):
                    excerpt = sent.strip()[:120]
                    break
        qs.append({"q": q, "ai_mentioned": ment, "ai_said": excerpt,
                   "ai_competitors": _competitors(ans, names)})
    return qs


def measure_naver(target: dict, queries: list[str], debug: bool = False) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {q: {"naver_found": None, "naver_rank": None} for q in queries}

    names = _names(target)
    res: dict[str, dict] = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not debug, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, viewport={"width": 1366, "height": 900})
        pg = ctx.new_page()
        for q in queries:
            try:
                pg.goto("https://search.naver.com/search.naver?query=" + urllib.parse.quote(q),
                        wait_until="domcontentloaded")
                pg.wait_for_timeout(1500)
                body = pg.inner_text("body")
                found = _mentioned(body, names)
                rank = None
                for sel in NAVER_PLACE_SEL:                 # 플레이스 리스트에서 우리 매장 위치
                    try:
                        items = pg.query_selector_all(sel)
                    except Exception:
                        items = []
                    if items:
                        for i, it in enumerate(items[:20], 1):
                            t = (it.inner_text() or "")
                            if _mentioned(t, names):
                                rank = i
                                found = True
                                break
                        if rank:
                            break
                res[q] = {"naver_found": found, "naver_rank": rank}
            except Exception:
                res[q] = {"naver_found": None, "naver_rank": None}
        ctx.close()
        b.close()
    return res


def collect(target: dict) -> dict:
    """AI + 네이버 측정 → signals(expose.score/prescribe 가 먹는 형식)."""
    qs = measure_ai(target)
    nv = measure_naver(target, [q["q"] for q in qs])
    for q in qs:
        q.update(nv.get(q["q"], {}))
    return {
        "queries": qs,
        "place": target.get("place", {"reviews": 0, "photos": 0, "comp_reviews_median": 0}),
        "blog_mentions": target.get("blog_mentions", 0),
    }
