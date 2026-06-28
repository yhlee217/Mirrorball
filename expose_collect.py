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


def _salon_names(target: dict) -> list[str]:
    s = target.get("salon", {}) or {}
    return [n for n in [s.get("name")] + (s.get("aliases") or []) if n]


def _designer_names(target: dict) -> list[str]:
    d = target.get("designer", {}) or {}
    return [n for n in [d.get("name")] + (d.get("aliases") or []) if n]


def _names(target: dict) -> list[str]:
    return _salon_names(target) + _designer_names(target)


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
    names, salon_n, des_n = _names(target), _salon_names(target), _designer_names(target)
    qs: list[dict] = []
    for q in target.get("questions", []) or []:
        ans = _claude(q + "\n\n(한국 미용실/헤어 디자이너 추천. 실제로 알려진 곳만, 모르면 모른다고 말해줘.)")
        ms, md = _mentioned(ans, salon_n), _mentioned(ans, des_n)   # 샵·디자이너 분리
        excerpt = ""
        if ms or md:
            for sent in re.split(r"(?<=[.!?\n])", ans):
                if _mentioned(sent, names):
                    excerpt = sent.strip()[:120]
                    break
        qs.append({"q": q, "ai_mentioned": ms or md, "ai_salon": ms, "ai_designer": md,
                   "ai_said": excerpt, "ai_competitors": _competitors(ans, names)})
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


# 대화체 질문 대신, 지역×시술로 '깨끗한' 발견 키워드를 만든다(공정한 측정).
# 단어 안의 '어디'(헤어디자이너) 같은 오절단 방지 — 토큰 파싱이 아니라 구조화 데이터에서 생성.
def naver_query(q: str) -> str:
    """(폴백) 대화체 → 키워드. 토큰 단위로만 불용어 제거(단어 내부는 안 건드림)."""
    filler = {"잘하는", "잘", "하는", "자연스럽게", "추천", "추천해줘", "해줘", "알려줘",
              "어디야", "어디", "근처", "좀", "있어", "봐주는", "해주는", "쪽", "까지",
              "곳", "찾아줘", "괜찮아", "인기", "인기있는", "그", "더"}
    toks = [t for t in re.split(r"[\s·,?]+", q) if t and t not in filler]
    s = " ".join(toks)
    if not re.search(r"미용실|헤어|디자이너|살롱", s):
        s += " 미용실"
    return s.strip()


def _regions(target: dict) -> list[str]:
    """측정 대상 지역(역) 목록 — regions(복수) 우선, 없으면 region(단일). 첫 번째가 실제 위치(primary)."""
    rs = target.get("regions") or ([target.get("region")] if target.get("region") else [])
    out, seen = [], set()
    for r in rs:
        r = (r or "").strip()
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def naver_keyword_queries(target: dict) -> list[dict]:
    """지역(역) × 시술 → 발견 키워드(깨끗). 각 항목에 시술(spec)·지역(region) 태그를 남긴다."""
    specs = [s.strip() for s in (target.get("specialties") or []) if s.strip()]
    out = []
    for region in _regions(target):
        for sp in specs:
            out.append({"q": f"{region} {sp}".strip(), "spec": sp, "region": region})
        out.append({"q": f"{region} 미용실".strip(), "spec": "미용실", "region": region})
    seen, uniq = set(), []
    for it in out:
        if it["q"] and it["q"] not in seen:
            seen.add(it["q"])
            uniq.append(it)
    return uniq


def measure_naver_canonical(target: dict, cid: str, csec: str, show: bool = False) -> list[dict]:
    """깨끗한 발견 키워드별 우리 순위 + 상위 경쟁사."""
    names = _names(target)
    res = []
    for kwd in naver_keyword_queries(target):
        kw, spec = kwd["q"], kwd["spec"]
        try:
            items = naver_local_search(kw, cid, csec)
            rank = _rank_in_items(items, names)
            top = [it["name"] for it in items[:3]]
            res.append({"q": kw, "spec": spec, "region": kwd.get("region"),
                        "naver_found": rank is not None, "naver_rank": rank, "top": top})
            if show:
                print(f"      네이버 '{kw}': {('우리 '+str(rank)+'위' if rank else '미노출')}"
                      f" | 상위: {', '.join(top) or '(결과 없음)'}")
        except Exception as e:
            res.append({"q": kw, "spec": spec, "region": kwd.get("region"),
                        "naver_found": None, "naver_rank": None, "top": []})
            if show:
                print(f"      네이버 '{kw}': 오류 {str(e)[:60]}")
    return res


# ── 실제 지도 순위(콜드) — 지역검색 API 는 top-5 만 줘서 '미노출'을 과장함. 플레이스 리스트 전체를 스크랩해 진짜 순위를 본다. ──
_RANK_UI = re.compile(r"^(광고|예약|영업\S*|리뷰|블로그|사진|쿠폰|길찾기|전화|저장|더보기|지도|"
                      r"필터|정렬|거리순|정확도순|관련도순|홈|메뉴|소식|N|예약확정|\d[\d.,]*)$")
# 결과가 적은 키워드에선 셀렉터가 UI 텍스트(영업시간·네이버페이 등)를 잡음 → 부분일치로 제거.
_RANK_NOISE = re.compile(r"영업|네이버페이|톡톡|예약확정|길찾기|\d{1,2}:\d{2}|영업\s*(중|종료|시작)")
# 업종 판별(미용실만 공정 비교) — 카테고리 텍스트로 1차 분류, 애매하면 Claude.
_SALON_CAT = re.compile(r"미용실|헤어|살롱|바버|이용원|펌|염색|컷")
_NONSALON_CAT = re.compile(r"네일|속눈썹|왁싱|피부|메이크업|퍼스널|골격|태닝|문신|마사지|"
                           r"에스테틱|반영구|타투|화장품|스파|체형|다이어트|두피문신|아이브로우")


def _classify_salon(ctx_text: str):
    """카테고리 텍스트 → 미용실 여부(True/False/None=모름)."""
    s, n = _SALON_CAT.search(ctx_text or ""), _NONSALON_CAT.search(ctx_text or "")
    if s:                       # 헤어+메이크업 복합도 미용실로 인정
        return True
    if n:
        return False
    return None


def _extract_place_items(page, depth: int) -> list[dict]:
    """현재 페이지에서 플레이스 리스트 항목(이름+업종판별)을 순서대로."""
    for sel in ("span.YwYLL", "span.place_bluelink", "li .place_bluelink",
                "li a[href*='/place/'] span", "li a[href*='/place/']"):
        try:
            els = page.query_selector_all(sel)
        except Exception:
            els = []
        seen, tmp = set(), []
        for e in els:
            name = (e.inner_text() or "").strip()
            if (not name or _RANK_UI.match(name) or _RANK_NOISE.search(name)
                    or not (1 < len(name) <= 25) or name in seen):
                continue
            try:                                     # 같은 리스트 항목(li) 전체 텍스트에서 업종 추출
                ctx = e.evaluate("el=>{const li=el.closest('li');return li?li.innerText:''}")
            except Exception:
                ctx = name
            seen.add(name)
            tmp.append({"name": name, "salon": _classify_salon(ctx)})
        if len(tmp) >= 3:
            return tmp[:depth]
    return []


def naver_place_list(page, query: str, depth: int = 40, debug: bool = False) -> list[dict]:
    """네이버 플레이스 리스트(지도/앱과 같은 랭킹) 전체를 순서대로 — 이름 + 업종판별.

    네이버가 연속 요청을 일부 막아(스로틀링) 빈 리스트가 나올 수 있어 URL별로 재시도한다.
    """
    q = urllib.parse.quote(query)
    for url in ("https://m.place.naver.com/place/list?query=%s&entry=pll" % q,
                "https://pcmap.place.naver.com/place/list?query=%s" % q):
        for attempt in (1, 2):                       # 스로틀링 대비 재시도
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2400 if attempt == 1 else 4000)
                body = (page.inner_text("body") or "")[:400]
                if "자동입력 방지" in body or "보안문자" in body or "비정상적인" in body:
                    if debug:
                        print(f"        [지도순위] '{query}': 차단(보안문자) — 잠시 후 재시도")
                    page.wait_for_timeout(3000)
                    continue
                for _ in range(8):                   # 끝까지 더 펼치기(깊게 다 스크랩)
                    page.mouse.wheel(0, 3600)
                    page.wait_for_timeout(500)
            except Exception:
                continue
            items = _extract_place_items(page, depth)
            if items:
                if debug:
                    print(f"        [지도순위] '{query}': {' > '.join(t['name'] for t in items[:10])}")
                return items
        if debug:
            print(f"        [지도순위] '{query}': 리스트 못읽음 ({url.split('//')[1][:20]})")
    return []


def _ai_drop_nonsalon(items: list[dict], query: str, debug: bool = False) -> None:
    """업종 애매(None)한 항목을 Claude 가 판단해 미용실 여부 채움(in-place)."""
    if not any(it["salon"] is None for it in items) or not shutil.which("claude"):
        return
    listing = "\n".join(f"{i}. {it['name']}" for i, it in enumerate(items, 1))
    ans = _claude("아래는 네이버 '" + query + "' 검색 결과 가게 목록이야.\n" + listing +
                  "\n\n이 중 '미용실/헤어살롱'이 아닌 곳(네일·속눈썹·왁싱·피부관리·메이크업·"
                  "퍼스널컬러·골격진단 등)의 번호만 콤마로 답해줘. 다 미용실이면 '없음'.", timeout=60)
    drop = {int(x) for x in re.findall(r"\d+", ans)}
    for i, it in enumerate(items, 1):
        if it["salon"] is None:
            it["salon"] = (i not in drop)            # 드랍목록에 없으면 미용실로 간주
    if debug and drop:
        names = [items[i - 1]["name"] for i in drop if 1 <= i <= len(items)]
        print(f"        [업종필터] '{query}' 제외(비미용실): {', '.join(names) or '없음'}")


def measure_naver_deep(target: dict, kw_items: list[dict], show: bool = False) -> dict:
    """발견 키워드별 '실제 지도 순위(콜드·익명) — 미용실만'. API top-5 한계 + 업종혼입 보완."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {}
    our = _names(target)
    out: dict[str, dict] = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not show, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, viewport={"width": 390, "height": 850})
        pg = ctx.new_page()
        for it in kw_items:
            items = naver_place_list(pg, it["q"], debug=show)
            _ai_drop_nonsalon(items, it["q"], debug=show)
            salons = [x for x in items if x["salon"] is not False]   # 미용실만 남겨 공정 비교
            rank = next((i for i, x in enumerate(salons, 1)
                         if any(n and n in x["name"] for n in our)), None)
            out[it["q"]] = {"rank": rank, "depth": len(salons), "raw_depth": len(items)}
            if show:
                print(f"        [지도순위] '{it['q']}': 미용실 {len(salons)}곳 중 "
                      f"{('우리 '+str(rank)+'위' if rank else '미노출')}")
        ctx.close()
        b.close()
    return out


def naver_name_baseline(target: dict, cid: str, csec: str) -> dict:
    """이름으로 검색했을 때 존재/순위 — '존재하는데 발견검색엔 안 뜸'을 구분."""
    salon = (target.get("salon", {}) or {}).get("name", "")
    region = (_regions(target) or [""])[0]           # 실제 위치(primary)로 이름 검색
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


# ── 플레이스 자산(리뷰·사진) — 공식 API 가 안 줘서 스크랩. CSS 대신 '텍스트 패턴'으로(덜 깨짐). ──
# 네이버는 큰 수를 '1.2천', '3.4만' 처럼 줄여 표기 — 숫자 캡처에 천/만 단위를 포함시킨다.
_CNT = r"([\d.,]+\s*[천만]?)"


def _kor_num(s: str) -> int:
    """'1,234' / '1.2천' / '3.4만' / '1만2천' → 정수."""
    if not s:
        return 0
    s = s.strip().replace(",", "")
    total, m = 0, re.findall(r"([\d.]+)\s*([천만]?)", s)
    if not m:
        return 0
    matched = False
    for num, unit in m:
        if not num:
            continue
        matched = True
        v = float(num)
        v *= {"천": 1000, "만": 10000, "": 1}.get(unit, 1)
        total += v
    return int(round(total)) if matched else 0


def _num(m) -> int:
    return _kor_num(m.group(1)) if m else 0


def _ratingf(txt: str):
    m = re.search(r"(?:별점|평점|★)\s*([0-5](?:\.\d)?)", txt or "")
    return float(m.group(1)) if m else None


_STYLE_STOP = re.compile(r"휠체어|저장|영업|길찾기|예약|전화|주차|리뷰|블로그|쿠폰|메뉴|소식|지도|"
                         r"공유|네이버|더보기|home|photo")


def parse_styles(txt: str) -> list[str]:
    """네이버 '인기스타일' 태그 추출 — 플레이스가 어떤 시술로 인식되는지(키워드 처방의 핵심).

    inner_text 는 줄바꿈이 섞여 옴 → 먼저 공백/줄바꿈을 한 줄로 정규화한 뒤 파싱한다.
    형식: '인기스타일 <s1> 인기 <s2> 인기 <s3> …' (각 스타일 앞에 '인기').
    """
    t = re.sub(r"\s+", " ", txt or "")
    m = re.search(r"인기스타일\s+(.{1,120})", t)
    if not m:
        return []
    seg = _STYLE_STOP.split(m.group(1))[0]              # 첫 구조어 전까지만(잡텍스트 컷)
    out = []
    for p in re.split(r"\s*인기\s+", seg.strip()):
        p = re.sub(r"[\[\]]", " ", p).strip()
        p = re.split(r"\s{2,}", p)[0].strip()          # 첫 토큰군만
        # 마지막 스타일 뒤에 붙는 대표시술 칩(커트·염색 등) 제거 — '펌'은 스타일이라 보존
        p = re.split(r"\s(?:커트|염색|클리닉|드라이|탈색|매직|스타일링|두피)", p)[0].strip()
        if p and len(p) <= 16 and p not in out:
            out.append(p)
    return out[:6]


def parse_place_text(txt: str) -> dict:
    """네이버 검색/플레이스 텍스트 → 리뷰·사진 수(방문자+블로그 리뷰 합)."""
    visit = _num(re.search(r"방문자\s*리뷰\s*" + _CNT, txt or ""))
    blog = _num(re.search(r"블로그\s*리뷰\s*" + _CNT, txt or ""))
    reviews = visit + blog
    if not reviews:                                # '리뷰 1,234' 단일 표기 폴백
        reviews = _num(re.search(r"리뷰\s*" + _CNT, txt or ""))
    photos = 0                                     # 사진 라벨 후보 여러 개 시도(네이버 표기 변동)
    for pat in (r"사진/?동?영?상?\s*" + _CNT, r"사진\s*" + _CNT,
                r"포토\s*" + _CNT, _CNT + r"\s*장의?\s*사진"):
        photos = _num(re.search(pat, txt or ""))
        if photos:
            break
    return {"reviews": reviews, "visitor_reviews": visit, "blog_reviews": blog,
            "photos": photos, "rating": _ratingf(txt)}


# 플레이스 ID 추출 패턴: 검색결과·플레이스 링크에서 매장 고유 ID 를 뽑는다.
_PLACE_ID_RE = re.compile(r"(?:hairshop|beauty|place|restaurant)/(\d{6,})")


def _find_place_id(page) -> str | None:
    """검색결과 페이지 링크/HTML 에서 플레이스 고유 ID 추출(사진 탭 진입용)."""
    try:                                           # 1) place 링크 href
        for a in page.query_selector_all("a[href*='place'], a[href*='pcmap']"):
            href = a.get_attribute("href") or ""
            m = (_PLACE_ID_RE.search(href)
                 or re.search(r"[?&]id=(\d{6,})", href)
                 or re.search(r"/(\d{6,})", href))
            if m:
                return m.group(1)
    except Exception:
        pass
    try:                                           # 2) iframe src(엔트리/플레이스 패널)
        for fr in page.query_selector_all("iframe"):
            src = fr.get_attribute("src") or ""
            m = _PLACE_ID_RE.search(src) or re.search(r"[?&]id=(\d{6,})", src)
            if m:
                return m.group(1)
    except Exception:
        pass
    try:                                           # 3) 전체 HTML 폴백
        m = _PLACE_ID_RE.search(page.content() or "")
        return m.group(1) if m else None
    except Exception:
        return None


def _place_page_text(page, place_id: str, tab: str = "home") -> str:
    """플레이스 페이지(홈/사진 탭) 본문 텍스트. 호스트·업종 경로를 순서대로 시도."""
    for host in ("m.place.naver.com", "pcmap.place.naver.com"):
        for kind in ("place", "hairshop", "beauty"):
            url = "https://%s/%s/%s/%s" % (host, kind, place_id, tab)
            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(1300)
                t = page.inner_text("body")
                if t and len(t) > 60 and "페이지를 찾을 수 없습니다" not in t:
                    return t
            except Exception:
                continue
    return ""


def _around(txt: str, kw: str, span: int = 36) -> str:
    """진단용: 키워드 주변 텍스트(사진/리뷰 표기 형태 확인)."""
    i = (txt or "").find(kw)
    if i < 0:
        return f"'{kw}' 없음"
    s = max(0, i - 8)
    return re.sub(r"\s+", " ", txt[s:i + span]).strip()


# 네이버는 사진 '총계'를 텍스트로 안 줌(탭 라벨뿐) → 사진 탭 썸네일을 실측 카운트한다.
# 콘텐츠 사진은 네이버 이미지 CDN(pstatic/phinf) 에서 옴 — UI 아이콘과 구분된다.
_PHOTO_IMG_SEL = ["img[src*='pstatic.net']", "img[src*='phinf']",
                  "div[class*='photo'] img", "a[href*='photo'] img"]


def _count_photos(page, place_id: str) -> int | None:
    """사진 탭 썸네일 수(지연로딩 스크롤로 펼쳐 카운트). 진입 실패 시 None(미측정)."""
    if not _place_page_text(page, place_id, "photo"):   # 사진 탭으로 이동
        return None
    try:
        for _ in range(6):                              # 지연 로딩 더 펼치기
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(700)
    except Exception:
        pass
    best = 0
    for sel in _PHOTO_IMG_SEL:
        try:
            best = max(best, len(page.query_selector_all(sel)))
        except Exception:
            pass
    return best or None


def scrape_place_assets(page, name: str, region: str = "", debug: bool = False) -> dict:
    """한 매장의 리뷰·사진 수. 검색 → 플레이스 페이지 진입(사진은 사진 탭에서 정확히)."""
    q = (name + " " + region).strip()
    try:
        page.goto("https://search.naver.com/search.naver?query=" + urllib.parse.quote(q),
                  wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        txt = page.inner_text("body")
    except Exception:
        return {"name": name, "found": None}
    d = parse_place_text(txt)                       # 검색결과 본문에서 리뷰·별점 1차 추정
    d["name"] = name
    d["found"] = (name.split()[0] in txt) if name else False
    d["styles"] = parse_styles(txt)                 # 인기스타일 태그(키워드 처방용)
    d["photos"] = None                              # 사진은 텍스트로 못 잡음 → 썸네일 실측만 신뢰

    pid = _find_place_id(page)                       # 2차: 플레이스 페이지에서 정확히
    if pid:
        d["place_id"] = pid
        home = _place_page_text(page, pid, "home")
        if home:
            hd = parse_place_text(home)
            for k in ("reviews", "visitor_reviews", "blog_reviews", "rating"):
                if hd.get(k):
                    d[k] = hd[k]
            if not d.get("styles"):                  # 검색 본문에 없으면 플레이스 홈에서
                d["styles"] = parse_styles(home)
            d["found"] = True
        d["photos"] = _count_photos(page, pid)       # 사진 탭 썸네일 실측(None=미측정)
    if debug:
        print(f"        [진단] {name}: place_id={pid} · 리뷰={d.get('reviews')}"
              f" · 별점={d.get('rating')} · 사진(썸네일)={d.get('photos')}"
              f" · 인기스타일={d.get('styles') or '(없음)'}")
    return d


def _median(xs: list[int]) -> int:
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else 0


def measure_place_assets(target: dict, cid: str, csec: str, debug: bool = False) -> dict:
    """우리 + 상위 경쟁사 5곳의 리뷰·사진 비교 + '따라잡기' 계산."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return {"measured": False}
    salon = (_salon_names(target) or [""])[0]
    region = (_regions(target) or [""])[0]           # 실제 위치(primary)의 이웃 경쟁사
    names = _names(target)
    key = (region + " 미용실").strip()
    try:
        comp_names = [it["name"] for it in naver_local_search(key, cid, csec, display=5)
                      if not any(n in it["name"] for n in names)][:5]
    except Exception:
        comp_names = []

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not debug, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=_UA, viewport={"width": 1366, "height": 900})
        pg = ctx.new_page()
        ours = scrape_place_assets(pg, salon, region, debug=debug)
        comps = [scrape_place_assets(pg, c, debug=debug) for c in comp_names]
        if debug:
            print(f"      우리({salon}): 리뷰 {ours.get('reviews')} · 사진 {ours.get('photos')} · 별점 {ours.get('rating')}")
            for c in comps:
                print(f"      경쟁 {c['name']}: 리뷰 {c.get('reviews')} · 사진 {c.get('photos')}")
        ctx.close()
        b.close()

    comp_rev = [c.get("reviews", 0) for c in comps if c.get("found")]
    med_rev = _median(comp_rev)
    our_rev, our_pho = ours.get("reviews", 0), ours.get("photos")   # 사진: int 또는 None(미측정)
    comp_pho = [c.get("photos") for c in comps if c.get("photos") is not None]
    med_pho = _median(comp_pho) if comp_pho else None
    return {
        "measured": True if ours.get("found") else False,
        "reviews": our_rev, "photos": our_pho, "rating": ours.get("rating"),
        "styles": ours.get("styles") or [],          # 우리 인기스타일(키워드 처방용)
        "comp_reviews_median": med_rev,
        "comp_photos_median": med_pho,
        "catch_up_reviews": max(0, med_rev - our_rev),
        "competitors": [{"name": c["name"], "reviews": c.get("reviews", 0),
                         "photos": c.get("photos"), "styles": c.get("styles") or []}
                        for c in comps if c.get("found")],
    }


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
    qs = measure_ai(target)                           # AI: 대화체 질문(손님 말투)
    base, nq = {}, []
    if cid and csec:
        nq = measure_naver_canonical(target, cid, csec, show=show)   # 네이버: 깨끗한 발견 키워드
        base = naver_name_baseline(target, cid, csec)
        if base.get("name_rank"):
            print(f"  · 이름 검색('{base.get('name_query')}'): {base['name_rank']}위로 존재 ✓")
        elif base.get("name_found") is False:
            print(f"  · 이름 검색('{base.get('name_query')}'): 상위에 안 보임 — 등록·정보 확인 필요")

    if target.get("_rank") and nq:                   # --rank: API top-5 한계 보완(실제 지도 순위, 전 지역)
        print(f"  · 네이버 지도 실제 순위(콜드·익명) 측정 중… [{len(nq)}개 키워드, 느림]")
        deep = measure_naver_deep(target, nq, show=show)
        for x in nq:
            d = deep.get(x["q"])
            if not d:
                continue
            x["naver_rank_api"] = x.get("naver_rank")    # API(top-5) 결과는 따로 보존
            x["naver_depth"] = d["depth"]
            if d["rank"]:                                # 실제 리스트에서 찾으면 그 순위로 갱신
                x["naver_found"], x["naver_rank"] = True, d["rank"]
            elif d["depth"] >= 10 and not x.get("naver_rank"):
                x["naver_found"] = False                 # 충분히 깊게 봤는데 없음 = 진짜 미노출

    place = target.get("place")                      # 사람이 채웠으면 사용
    if target.get("_place") and cid and csec:        # --place: 플레이스 리뷰·사진 스크랩
        print("  · 플레이스 자산(리뷰·사진) 스크랩 중…")
        place = measure_place_assets(target, cid, csec, debug=show)
    if not place:
        place = {"measured": False}
    return {
        "queries": qs,
        "naver_queries": nq,
        "place": place,
        "blog_mentions": target.get("blog_mentions"),   # None = 미측정
        "name_baseline": base,
        "measured_by": f"AI(Claude CLI) + 네이버({used}) · 발견키워드 {len(nq)}개",
    }
