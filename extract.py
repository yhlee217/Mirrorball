"""추출 로직 — substring 매칭이면 충분 (NER/임베딩 금지).

- mentioned: 디자이너/매장 name+aliases 중 하나라도 등장하는지
- context: 언급된 문장 ±1문장
- citations: 엔진 반환 인용 + 본문 URL 정규식 병합
- competitors_mentioned: "○○헤어/△△살롱" 휴리스틱 (완벽하지 않아도 됨)
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# 문장 분리 (한국어 종결부호 + 줄바꿈). 완벽할 필요 없음.
_SENT_SPLIT = re.compile(r"(?<=[.!?。…\n])\s*")
_URL_RE = re.compile(r"https?://[^\s)>\]\"'」』）]+")
# 경쟁 매장/디자이너 후보 휴리스틱: 고유명사(공백 없는 연속어) + 업종어.
# 공백을 허용하지 않아 앞 단어가 딸려오는 것을 막는다 ("다 라온살롱" → "라온살롱").
# 업종 접미사는 한 곳에 모음 — 복제 시 네일/속눈썹 등으로 교체 (예: 네일/네일샵/속눈썹/왁싱).
COMPETITOR_SUFFIXES = ("헤어", "살롱", "미용실", "뷰티", "바버", "스튜디오")
_COMPETITOR_RE = re.compile(
    r"[가-힣A-Za-z0-9]+(?:" + "|".join(COMPETITOR_SUFFIXES) + r")"
)


def normalize(s: str) -> str:
    """공백/특수문자 제거 + 소문자화. 매칭 비교용."""
    return re.sub(r"[\s\W_]+", "", s or "").lower()


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def is_mentioned(text: str, names: list[str]) -> bool:
    norm_text = normalize(text)
    return any(normalize(n) and normalize(n) in norm_text for n in names)


def mention_context(text: str, names: list[str]) -> str | None:
    """이름이 등장하는 문장 ±1문장을 반환. 없으면 None."""
    sentences = split_sentences(text)
    norm_names = [normalize(n) for n in names if normalize(n)]
    for i, sent in enumerate(sentences):
        norm_sent = normalize(sent)
        if any(n in norm_sent for n in norm_names):
            lo, hi = max(0, i - 1), min(len(sentences), i + 2)
            return " ".join(sentences[lo:hi])
    return None


def _clean_url(url: str) -> str:
    return url.rstrip(".,);]\"'」』")


def extract_citations(text: str, engine_citations: list[str]) -> list[str]:
    """엔진 인용 + 본문 URL 을 병합, 순서 보존 중복제거."""
    seen: list[str] = []
    for url in list(engine_citations or []) + _URL_RE.findall(text or ""):
        url = _clean_url(url)
        if url and url not in seen:
            seen.append(url)
    return seen


def extract_competitors(text: str, own_names: list[str]) -> list[str]:
    """다른 미용실/디자이너 명칭 후보. 자기 자신은 제외."""
    own = {normalize(n) for n in own_names if normalize(n)}
    found: list[str] = []
    for m in _COMPETITOR_RE.findall(text or ""):
        cand = m.strip()
        nc = normalize(cand)
        if not nc or nc in own:
            continue
        # 자기 매장명의 부분/상위 문자열이면 제외
        if any(nc in o or o in nc for o in own):
            continue
        if cand not in found:
            found.append(cand)
    return found


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def analyze(
    text: str,
    designer_names: list[str],
    salon_names: list[str],
    engine_citations: list[str],
) -> dict:
    """한 응답에 대한 종합 추출 결과."""
    all_own = list(designer_names) + list(salon_names)
    mentioned = is_mentioned(text, all_own)
    return {
        "mentioned": mentioned,
        "context": mention_context(text, all_own) if mentioned else None,
        "citations": extract_citations(text, engine_citations),
        "competitors_mentioned": extract_competitors(text, all_own),
    }
