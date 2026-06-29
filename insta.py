#!/usr/bin/env python3
"""인스타 발견 지표 엔진 — 언급·점유율(SoV)·인게이지먼트 → 점수·추세(결정적).

신호(insta_collect.collect) → score(0~100) → 추세(history) → instagram.yaml(앱이 읽음).
expose.py 와 같은 철학: **측정한 차원만** 점수에 넣고, 못 본 것(개인계정 등)은 0 으로 단정 안 함.

정직성: '언급량'은 해시태그 최근 샘플 합(총량 아님). SoV 는 '브랜드 해시태그 기준'으로 정의.
개인/비공개 경쟁사는 measured=False → 분모에서 제외하고 coverage 로 표기.
"""

from __future__ import annotations

from datetime import date

# ── 가중치(합 100). 사장님 1순위가 '점유율' 이라 SoV 비중을 가장 크게. ──
W_SOV = 45        # 경쟁 대비 우리 언급 점유율
W_ENGAGE = 30     # 게시물당 인게이지먼트(경쟁 중위 대비)
W_PRESENCE = 25   # 우리 브랜드 언급량(절대 존재감)

_PRESENCE_BASE = 20   # 브랜드 언급+태그 이 정도면 presence 만점(근사 기준)


def _median(xs: list) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def _measured_comps(sig: dict) -> list[dict]:
    return [c for c in (sig.get("competitors") or []) if c]


def share_of_voice(sig: dict):
    """우리 브랜드 언급 ÷ (우리 + 측정된 경쟁사 언급). (sov 0~1, coverage 측정 경쟁수) 반환."""
    our = (sig.get("our") or {}).get("brand_count")
    comp_counts = [c.get("brand_count") for c in _measured_comps(sig)
                   if c.get("brand_count") is not None]
    if our is None or not comp_counts:
        return None, 0
    total = our + sum(comp_counts)
    return (our / total if total else 0.0), len(comp_counts)


def _engage_index(sig: dict):
    """우리 인게이지먼트 ÷ 경쟁 중위(측정된 비즈니스 계정만). 0~1(초과는 1)."""
    our = (sig.get("our") or {}).get("engagement")
    comp = _median([c.get("engagement") for c in _measured_comps(sig)
                    if c.get("engagement") is not None])
    if our is None or not comp:
        return None
    return min(1.0, our / comp)


def measured_dims(sig: dict) -> dict:
    our = sig.get("our") or {}
    sov, _ = share_of_voice(sig)
    return {
        "sov": sov is not None,
        "engage": _engage_index(sig) is not None,
        "presence": our.get("brand_count") is not None or our.get("mentions") is not None,
    }


def score(sig: dict):
    """signals → 0~100 인스타 발견 점수. **측정한 차원만** 가중 평균."""
    if not sig or sig.get("measured") is False:
        return None
    our = sig.get("our") or {}
    m = measured_dims(sig)
    parts = []
    if m["sov"]:
        sov, _ = share_of_voice(sig)
        parts.append((W_SOV, sov))
    if m["engage"]:
        parts.append((W_ENGAGE, _engage_index(sig)))
    if m["presence"]:
        signal = (our.get("brand_count") or 0) + (our.get("mentions") or 0)
        parts.append((W_PRESENCE, min(1.0, signal / _PRESENCE_BASE)))
    if not parts:
        return None
    wsum = sum(w for w, _ in parts)
    return round(100 * sum(w * v for w, v in parts) / wsum)


def hashtag_trends(sig: dict, prev: dict | None = None) -> list[dict]:
    """시장 해시태그(지역×스타일)의 지난 측정 대비 샘플 증감 — 뜨는 스타일 포착."""
    prevmap = {h.get("tag"): h.get("count") for h in (prev or {}).get("hashtags", []) or []}
    out = []
    for h in sig.get("hashtags") or []:
        tag, cur = h.get("tag"), h.get("count")
        pc = prevmap.get(tag)
        delta = (cur - pc) if (cur is not None and pc is not None) else None
        out.append({"tag": tag, "count": cur, "engagement": h.get("engagement"),
                    "prev_count": pc, "delta": delta})
    out.sort(key=lambda x: (x["delta"] is not None, x["delta"] or 0, x["count"] or 0), reverse=True)
    return out


def insta_changes(sig: dict, prev: dict | None, today: date | None = None) -> dict:
    """지난 측정 대비 점유율·언급량 변화(신뢰 증명)."""
    today = today or date.today()
    hist = (prev or {}).get("history") or []
    prior = next((h for h in reversed(hist) if h.get("date") != str(today) and "sov" in h), None)
    if not prior:
        return {}
    sov, _ = share_of_voice(sig)
    cur_brand = (sig.get("our") or {}).get("brand_count")
    try:
        weeks = max(0, (today - date.fromisoformat(prior["date"])).days) // 7
    except Exception:
        weeks = None
    out = {"weeks": weeks, "since": prior["date"]}
    if sov is not None and prior.get("sov") is not None:
        out["sov_prev"], out["sov"] = prior["sov"], round(sov, 3)
        out["sov_delta"] = round(sov - prior["sov"], 3)
    if cur_brand is not None and prior.get("brand_count") is not None:
        out["brand_prev"], out["brand"] = prior["brand_count"], cur_brand
        out["brand_delta"] = cur_brand - prior["brand_count"]
    return out


def build_insta(sig: dict, prev: dict | None = None, today: date | None = None) -> dict:
    """signals → instagram.yaml 구조(점수·점유율·트렌드·추세)."""
    today = today or date.today()
    s = score(sig)
    sov, coverage = share_of_voice(sig)
    changes = insta_changes(sig, prev, today)
    hist = list((prev or {}).get("history", []) or [])
    if s is not None and (not hist or hist[-1].get("date") != str(today)):
        hist.append({"date": str(today), "score": s,
                     "sov": round(sov, 3) if sov is not None else None,
                     "brand_count": (sig.get("our") or {}).get("brand_count")})
    hist = hist[-12:]
    return {
        "generated_at": str(today),
        "score": s,
        "measured": measured_dims(sig),
        "sov": round(sov, 3) if sov is not None else None,
        "sov_coverage": coverage,                 # 점유율 분모에 든 경쟁 수(정직성)
        "engage_index": _engage_index(sig),
        "our": sig.get("our") or {},
        "competitors": sig.get("competitors") or [],
        "hashtags": hashtag_trends(sig, prev),
        "changes": changes,
        "note": sig.get("measured_by") or sig.get("note"),
        "history": hist,
    }
