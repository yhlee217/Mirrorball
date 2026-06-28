#!/usr/bin/env python3
"""발견 케어 측정기 — AI(Claude CLI) + 네이버(공개 검색 스크랩). 실행 환경에서만 동작.

- measure_ai: 질문을 Claude CLI(`claude -p`, 키 0)에 던지고 답변에서 디자이너/매장 언급 추출.
- measure_naver: search.naver.com 공개 검색을 스크랩해 노출/순위 추정(로그인 불필요).
  네이버 DOM 셀렉터는 바뀌므로, 안 잡히면 --debug 로 확인해 NAVER_PLACE_SEL 만 고친다.

substring 매칭으로 충분(NER 불필요). 측정 후 expose.build_exposure 가 점수·처방·추세를 만든다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def naver_keys(target: dict) -> tuple[str | None, str | None]:
    """네이버 키 우선순위: target.naver → secrets/naver.yaml(git 제외) → 환경변수."""
    nk = target.get("naver") or {}
    cid, csec = nk.get("client_id"), nk.get("client_secret")
    if not (cid and csec):
        p = _ROOT / "secrets" / "naver.yaml"
        if p.exists():
            import yaml
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            cid = cid or d.get("client_id")
            csec = csec or d.get("client_secret")
    return (cid or os.getenv("NAVER_CLIENT_ID")), (csec or os.getenv("NAVER_CLIENT_SECRET"))

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


# ── 네이버 지역검색 OpenAPI (무료 키, JSON) — 스크래핑보다 안정적. 발견·순위 측정의 1순위. ──
def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _rank_in_items(items: list[dict], names: list[str]) -> int | None:
    """지역검색 결과(상위 N) 중 우리 매장이 몇 번째인지(없으면 None)."""
    for i, it in enumerate(items, 1):
        nm = it.get("name", "")
        if any(n and n in nm for n in names):
            return i
    return None


def naver_local_search(query: str, cid: str, csec: str, display: int = 5, timeout: int = 10) -> list[dict]:
    url = "https://openapi.naver.com/v1/search/local.json?display=%d&query=%s" % (
        display, urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [{"name": _strip_tags(it.get("title")), "category": it.get("category", ""),
             "road": it.get("roadAddress", "")} for it in data.get("items", [])]


# 대화체 질문 → 지역검색용 키워드(불용어 제거). "…잘하는 미용실 추천해줘" → "… 미용실"
_NAVER_FILLER = re.compile(
    r"(잘\s*하는|자연스럽게|추천\s*해줘|추천|알려줘|어디야|어디|근처|좀|있어|봐주는|해주는|쪽|까지)")


def naver_query(q: str) -> str:
    s = _NAVER_FILLER.sub(" ", q)
    s = re.sub(r"[?·,]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not re.search(r"미용실|헤어|디자이너|살롱", s):
        s += " 미용실"
    return s


def measure_naver_api(target: dict, cid: str, csec: str, show: bool = False) -> dict:
    names = _names(target)
    res: dict[str, dict] = {}
    for q in target.get("questions", []) or []:
        kw = naver_query(q)
        try:
            items = naver_local_search(kw, cid, csec)
            rank = _rank_in_items(items, names)
            res[q] = {"naver_found": rank is not None, "naver_rank": rank, "naver_kw": kw}
            if show:
                top = ", ".join(it["name"] for it in items[:3]) or "(결과 없음)"
                print(f"      네이버 '{kw}': {('우리 '+str(rank)+'위' if rank else '미노출')} | 상위: {top}")
        except Exception as e:
            res[q] = {"naver_found": None, "naver_rank": None, "naver_kw": kw}
            if show:
                print(f"      네이버 '{kw}': 오류 {str(e)[:60]}")
    return res


def naver_name_baseline(target: dict, cid: str, csec: str) -> dict:
    """이름으로 검색했을 때 존재/순위 — '존재하는데 발견검색엔 안 뜸'을 구분."""
    salon = (target.get("salon", {}) or {}).get("name", "")
    region = target.get("region", "")
    q = (salon + " " + region).strip() or salon
    if not q:
        return {"name_found": None, "name_rank": None}
    try:
        items = naver_local_search(q, cid, csec)
        rank = _rank_in_items(items, _names(target))
        return {"name_found": rank is not None, "name_rank": rank, "name_query": q}
    except Exception:
        return {"name_found": None, "name_rank": None, "name_query": q}


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
    """AI + 네이버 측정 → signals. 네이버는 OpenAPI(키) 우선, 없으면 스크랩 폴백.

    네이버 키: target.naver.client_id/secret 또는 환경변수 NAVER_CLIENT_ID/SECRET.
    플레이스 리뷰·사진은 공식 API 가 안 줘서 별도 — 없으면 '미측정'으로 둔다(0 단정 금지).
    """
    claude_ok = shutil.which("claude") is not None
    cid, csec = naver_keys(target)
    used = "naver-openapi" if (cid and csec) else "scrape"
    # 측정이 실제로 됐는지 투명하게(점수 0 이 '진짜 0위'인지 '측정 실패'인지 구분)
    print("  · AI: " + ("Claude CLI ✓" if claude_ok else "Claude CLI 없음 → AI 측정 안 됨(설치 필요)"))
    print("  · 네이버: " + ("OpenAPI 키 ✓" if (cid and csec) else
                            "키 없음 → 스크랩 폴백(secrets/naver.yaml 또는 환경변수)"))

    show = bool(target.get("_show"))
    qs = measure_ai(target)
    if cid and csec:
        nv = measure_naver_api(target, cid, csec, show=show)
        base = naver_name_baseline(target, cid, csec)
        if base.get("name_rank"):
            print(f"  · 이름 검색('{base.get('name_query')}'): {base['name_rank']}위로 존재 ✓")
        elif base.get("name_found") is False:
            print(f"  · 이름 검색('{base.get('name_query')}'): 상위에 안 보임 — 등록·정보 확인 필요")
    else:
        nv = measure_naver(target, [q["q"] for q in qs])
        base = {}
    for q in qs:
        q.update(nv.get(q["q"], {}))

    place = target.get("place")                      # 사람이 채웠으면 사용, 아니면 미측정
    if not place:
        place = {"measured": False}
    return {
        "queries": qs,
        "place": place,
        "blog_mentions": target.get("blog_mentions"),   # None = 미측정
        "name_baseline": base,
        "measured_by": f"AI(Claude CLI) + 네이버({used}) · {len(qs)}개 질문",
    }
