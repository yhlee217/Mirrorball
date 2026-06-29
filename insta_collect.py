#!/usr/bin/env python3
"""인스타 발견 수집기 — Instagram Graph API(공식, 비즈니스 계정). 유령계정·스크래핑 아님.

- 네트워크는 _graph() 한 곳에만. 나머지는 응답 JSON → 신호로 바꾸는 '순수 파서'라 토큰 없이 테스트됨.
- 한계(정직): 해시태그 '총 게시물 수'는 API 가 안 줌 → 최근 게시물 '샘플 수'로 근사.
  경쟁사가 개인/비공개 계정이면 안 보임(measured=False 로 둠).

자격증명: secrets/instagram.yaml (ig_user_id, access_token, hashtags[], competitors[]).
발급 절차: scripts/INSTAGRAM_SETUP.md / .html
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com/v23.0"


# ── 자격증명 ────────────────────────────────────────────────────────────────
def insta_keys(target: dict | None = None) -> dict:
    """secrets/instagram.yaml → {ig_user_id, access_token, hashtags, competitors, ...}."""
    cfg = dict((target or {}).get("instagram") or {})
    p = _ROOT / "secrets" / "instagram.yaml"
    if p.exists():
        import yaml
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for k, v in d.items():
            cfg.setdefault(k, v)
    return cfg


# ── 네트워크 (유일한 I/O 지점) ────────────────────────────────────────────────
def _graph(path: str, params: dict, timeout: int = 15) -> dict:
    url = "%s/%s?%s" % (GRAPH, path.lstrip("/"), urllib.parse.urlencode(params))
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 순수 파서 (토큰 불필요 · 테스트 대상) ──────────────────────────────────────
def _eng_list(media: list[dict]) -> list[int]:
    """게시물들의 인게이지먼트(좋아요+댓글) 리스트."""
    out = []
    for m in media or []:
        if m is None:
            continue
        out.append(int(m.get("like_count", 0) or 0) + int(m.get("comments_count", 0) or 0))
    return out


def _avg(xs: list[int]):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def parse_account(js: dict) -> dict:
    """내 계정 응답 → {username, followers, media_count, posts, engagement}."""
    media = ((js.get("media") or {}).get("data")) or []
    eng = _eng_list(media)
    return {
        "username": js.get("username"),
        "followers": js.get("followers_count"),
        "media_count": js.get("media_count"),
        "posts": len(media),
        "engagement": _avg(eng),
    }


def parse_business_discovery(js: dict) -> dict | None:
    """business_discovery 응답 → 경쟁 비즈니스 계정 지표. 없으면 None(개인/비공개)."""
    bd = js.get("business_discovery")
    if not bd:
        return None
    media = ((bd.get("media") or {}).get("data")) or []
    return {
        "username": bd.get("username"),
        "followers": bd.get("followers_count"),
        "media_count": bd.get("media_count"),
        "engagement": _avg(_eng_list(media)),
        "measured": True,
    }


def parse_hashtag_media(js: dict) -> dict:
    """해시태그 recent/top media 응답 → {count(샘플 수), engagement(평균)}."""
    media = js.get("data") or []
    return {"count": len(media), "engagement": _avg(_eng_list(media))}


# ── 수집기 (네트워크 + 파서 조합) ─────────────────────────────────────────────
def _account(ig: str, token: str) -> dict:
    fields = "username,followers_count,media_count,media.limit(12){like_count,comments_count}"
    return parse_account(_graph(ig, {"fields": fields, "access_token": token}))


def _business(ig: str, token: str, username: str) -> dict | None:
    fields = ("business_discovery.username(%s){followers_count,media_count,"
              "media.limit(12){like_count,comments_count}}" % username)
    try:
        return parse_business_discovery(_graph(ig, {"fields": fields, "access_token": token}))
    except Exception:
        return None                       # 개인계정/비공개/오류 → 미측정


def _hashtag_id(ig: str, token: str, name: str) -> str | None:
    js = _graph("ig_hashtag_search", {"user_id": ig, "q": name, "access_token": token})
    data = js.get("data") or []
    return data[0].get("id") if data else None


def _hashtag(ig: str, token: str, name: str) -> dict:
    try:
        hid = _hashtag_id(ig, token, name)
        if not hid:
            return {"tag": name, "count": None, "engagement": None}
        fields = "like_count,comments_count,caption"
        js = _graph("%s/recent_media" % hid,
                    {"user_id": ig, "fields": fields, "access_token": token})
        d = parse_hashtag_media(js)
        d["tag"] = name
        return d
    except Exception:
        return {"tag": name, "count": None, "engagement": None}


def _mentions(ig: str, token: str) -> int | None:
    """우리 계정이 태그된 미디어 수(이번 호출 시점 샘플)."""
    try:
        js = _graph("%s/tags" % ig, {"fields": "id", "access_token": token})
        return len(js.get("data") or [])
    except Exception:
        return None


def _brand_count(ig: str, token: str, tags: list[str]) -> int | None:
    """브랜드 해시태그들의 최근 샘플 합(언급량 근사). 태그 없으면 None."""
    tags = [t for t in (tags or []) if t]
    if not tags:
        return None
    total, seen = 0, False
    for t in tags:
        c = _hashtag(ig, token, t).get("count")
        if c is not None:
            total += c
            seen = True
    return total if seen else None


def collect(target: dict | None = None) -> dict:
    """Graph API → 인스타 신호. '렌즈 계정(호출 주체)'과 '측정 대상(살롱)'을 분리.

    렌즈는 컨시어지 본인 비즈니스 계정이어도 됨 — 살롱 공개 데이터는 Business Discovery 로 봄.
    살롱 비공개 인사이트·정확한 멘션이 필요할 때만 lens_is_salon=true (렌즈=살롱 계정).
    """
    cfg = insta_keys(target)
    ig, token = cfg.get("ig_user_id"), cfg.get("access_token")
    if not (ig and token):
        return {"measured": False, "note": "instagram 키 없음 — secrets/instagram.yaml"}

    salon = cfg.get("salon") or {}
    salon_user = salon.get("username") or (target or {}).get("salon", {}).get("name")
    salon_tags = salon.get("hashtags") or cfg.get("brand_hashtags") or []
    comps = [c for c in (cfg.get("competitors") or []) if c]
    market = [t for t in (cfg.get("market_hashtags") or cfg.get("hashtags") or []) if t]
    market = market[:30]                                          # 7일당 30개 한도
    lens_is_salon = bool(cfg.get("lens_is_salon"))

    # 측정 대상(살롱): 공개 데이터는 디스커버리, 렌즈가 살롱이면 비공개까지
    if lens_is_salon:
        our = _account(ig, token)
        our["mentions"] = _mentions(ig, token)
        our["measured"] = True
    else:
        our = _business(ig, token, salon_user) if salon_user else None
        our = our or {"username": salon_user, "measured": False}
    our["brand_count"] = _brand_count(ig, token, salon_tags)

    hashtags = [_hashtag(ig, token, t) for t in market]           # 시장 트렌드(지역×스타일)
    competitors = []
    for c in comps:                                               # 경쟁 비즈니스 계정
        bd = _business(ig, token, c) or {"username": c, "measured": False}
        bd.setdefault("brand_count", _brand_count(ig, token, [c]))  # username 을 브랜드 태그로 근사
        competitors.append(bd)

    return {
        "measured": True,
        "lens_is_salon": lens_is_salon,
        "our": our,
        "hashtags": hashtags,
        "competitors": competitors,
        "measured_by": "Instagram Graph API · 시장태그 %d · 경쟁 %d%s"
                       % (len(market), len(comps), " · 살롱렌즈" if lens_is_salon else " · 외부렌즈"),
    }
