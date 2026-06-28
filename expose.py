#!/usr/bin/env python3
"""발견 케어(Discoverability) 엔진 — AI·네이버 노출 측정 → 점수 → 처방 → 추세.

손님이 "영등포 레이어드컷 잘하는 곳" 을 AI 에 묻거나 네이버에 검색할 때
하예원/살롱톤이 보이는가? 를 측정하고, 안 보이면 '이번 주 할 일' 까지 준다.

  측정(AI: Claude CLI · 네이버: 스크래핑)  →  signals
  signals  →  score(0~100)  →  prescribe(이번 주 액션)  →  exposure.yaml(앱이 읽음)
  매번 score 를 history 에 쌓아 '개선 추세' 를 본다.

비용 0 원칙: AI 는 Claude CLI(`claude -p`, 키 0), 네이버는 공개 검색 스크랩.
이 파일의 score()/prescribe() 는 결정적(LLM 불필요) — 측정값만 있으면 동작.

사용:
  python expose.py clients/hayewoni            # 측정 없이 기존 signals 로 점수·처방만(또는 샘플)
  python expose.py clients/hayewoni --measure  # AI/네이버 측정까지(브라우저·CLI 필요)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

# ── 점수 가중치(합 100). 한국 미용실 현실: 네이버 비중을 AI 보다 크게. ──
W_NAVER = 35     # 네이버 검색/플레이스에서 발견되는가
W_AI = 30        # AI 가 추천에 언급하는가
W_PLACE = 20     # 플레이스 자산(리뷰·사진) 충실도
W_BLOG = 15      # 최근 블로그 후기 노출


def _rate(hits: int, total: int) -> float:
    return (hits / total) if total else 0.0


def _place_measured(place: dict) -> bool:
    return bool(place) and place.get("measured") is not False and place.get("reviews") is not None


def _naver_items(sig: dict) -> list:
    """네이버 측정 대상: 깨끗한 발견키워드(naver_queries) 우선, 없으면 질문(naver_found)."""
    return sig.get("naver_queries") or sig.get("queries") or []


def measured_dims(sig: dict) -> dict:
    """어떤 차원을 실제로 측정했나(미측정과 '측정된 0'을 구분 — 정직성)."""
    qs = sig.get("queries") or []
    nv = _naver_items(sig)
    return {
        "ai": bool(qs),
        "naver": bool(nv) and any(x.get("naver_found") is not None for x in nv),
        "place": _place_measured(sig.get("place") or {}),
        "blog": sig.get("blog_mentions") is not None,
    }


def score(sig: dict):
    """signals → 0~100 발견 점수. **측정한 차원만** 가중 평균(미측정은 제외)."""
    qs = sig.get("queries", []) or []
    n = len(qs)
    m = measured_dims(sig)
    parts = []                                   # (weight, value 0~1)
    if m["ai"]:
        parts.append((W_AI, _rate(sum(1 for q in qs if q.get("ai_mentioned")), n)))
    if m["naver"]:
        nv = _naver_items(sig)
        k = len(nv) or 1
        nv_found = _rate(sum(1 for x in nv if x.get("naver_found")), k)
        ranks = [x["naver_rank"] for x in nv if x.get("naver_found") and x.get("naver_rank")]
        rank_q = (sum(max(0, 1 - (r - 1) / 10) for r in ranks) / len(ranks)) if ranks else 0.0
        parts.append((W_NAVER, 0.7 * nv_found + 0.3 * rank_q))
    if m["place"]:
        place = sig["place"]
        comp = place.get("comp_reviews_median") or 0
        reviews = place.get("reviews", 0)
        rev_ok = min(1.0, reviews / comp) if comp else min(1.0, reviews / 20)
        photos = place.get("photos")
        if photos is not None:                   # 사진 측정됐을 때만 반영, 아니면 리뷰만
            parts.append((W_PLACE, 0.6 * rev_ok + 0.4 * min(1.0, photos / 10)))
        else:
            parts.append((W_PLACE, rev_ok))
    if m["blog"]:
        parts.append((W_BLOG, min(1.0, sig["blog_mentions"] / 5)))
    if not parts:
        return None
    wsum = sum(w for w, _ in parts)
    return round(100 * sum(w * v for w, v in parts) / wsum)


def prescribe(sig: dict) -> list[dict]:
    """signals → '이번 주 할 일'(우선순위순). 가장 임팩트 큰 결손부터."""
    qs = sig.get("queries", []) or []
    n = len(qs) or 1
    place = sig.get("place", {}) or {}
    m = measured_dims(sig)
    out: list[dict] = []

    if m["naver"]:
        nv = _naver_items(sig)
        k = len(nv) or 1
        nv_found = sum(1 for x in nv if x.get("naver_found"))
        if nv_found / k < 0.5:
            out.append({"priority": 1, "area": "naver",
                        "title": "네이버 플레이스 정보 보강(업종·지역·시술 키워드)",
                        "why": f"발견 키워드 {k}개 중 {nv_found}개에서만 노출돼요",
                        "effort": "20분"})

    if not m["place"]:                 # 미측정 — 0 으로 단정하지 않고 '측정'을 액션으로
        out.append({"priority": 2, "area": "place",
                    "title": "네이버 플레이스 현황 측정(리뷰·사진·순위)",
                    "why": "정확한 진단을 위해 플레이스 수치를 한 번 측정해요(온머신 자동)",
                    "effort": "자동 1회"})
    else:
        reviews = place.get("reviews", 0)
        comp = place.get("comp_reviews_median") or 0
        if comp and reviews < comp:
            out.append({"priority": 2, "area": "review",
                        "title": f"방문 고객께 네이버 리뷰 요청(목표 {comp - reviews}건)",
                        "why": f"리뷰 {reviews}건 < 주변 경쟁 평균 {comp}건",
                        "effort": "고객당 30초"})
        elif reviews < 20:
            out.append({"priority": 2, "area": "review",
                        "title": "방문 고객께 네이버 리뷰 요청(목표 20건)",
                        "why": f"리뷰 {reviews}건 — 신규 고객 신뢰의 1순위",
                        "effort": "고객당 30초"})
        photos = place.get("photos")
        if photos is not None and photos < 10:
            out.append({"priority": 3, "area": "place",
                        "title": "플레이스 시술 사진 5장 추가(전후·스타일별)",
                        "why": f"사진 {photos}장 — 클릭률·체류에 직결",
                        "effort": "10분"})

    if m["ai"] and sum(1 for q in qs if q.get("ai_mentioned")) / n < 0.3:
        out.append({"priority": 4, "area": "ai",
                    "title": "프로필 페이지 + 디자이너 이름 후기로 웹 흔적 늘리기",
                    "why": "AI 가 아직 거의 언급 안 해요 — 웹에 인용할 정보가 적음",
                    "effort": "주 1회"})

    if not m["blog"] or sig.get("blog_mentions", 0) < 2:
        out.append({"priority": 5, "area": "blog",
                    "title": "이번 시술 후기 블로그/인스타 1건(지역+시술명 태그)",
                    "why": "최근 후기가 적어 검색·AI 모두에 신호가 약해요",
                    "effort": "15분"})

    out.sort(key=lambda x: x["priority"])
    return out[:3]                    # 한 번에 3개까지(부담 줄임)


def keyword_plan(sig: dict) -> list[dict]:
    """발견 키워드별 '이렇게 입력하세요' — 우리 인기스타일에 그 시술이 있나 + 상위 경쟁사 근거.

    핵심 인사이트: 손님이 'OO 레이어드컷'으로 검색하면 네이버는 그 시술을 '인기스타일'로
    가진 매장을 올림. 우리 인기스타일에 그 시술이 없으면 → 등록·후기로 심어야 노출됨.
    """
    nq = sig.get("naver_queries") or []
    place = sig.get("place") or {}
    my_str = " ".join(place.get("styles") or [])
    comp_styles = {c.get("name"): " ".join(c.get("styles") or [])
                   for c in (place.get("competitors") or [])}
    plans: list[dict] = []
    for x in nq:
        spec = x.get("spec")
        if not spec or spec == "미용실":
            continue
        kw, rank, top = x.get("q", spec), x.get("naver_rank"), (x.get("top") or [])
        has = bool(spec) and spec in my_str
        proof = [n for n in top if spec in comp_styles.get(n, "")]   # 이 시술을 가진 상위 경쟁사
        if rank and has:
            status, advice = "ok", f"{rank}위 유지 — 방문 후기에 '{spec}' 언급 계속 유도"
        elif not has:
            status = "gap"
            advice = (f"플레이스 시술메뉴에 '{spec}' 등록 + 방문 후기에 '{spec}' 키워드로 남겨달라 요청"
                      + (f" (상위 {proof[0]} 등이 이 키워드 보유)" if proof else ""))
        else:
            status = "near"
            advice = f"'{spec}'은 등록됐는데 미노출 — 최근 '{spec}' 시술 후기·사진을 늘려 신선도 ↑"
        plans.append({"keyword": kw, "spec": spec, "rank": rank, "status": status,
                      "has_style": has, "advice": advice, "proof": proof, "top": top[:3]})
    return plans


def build_exposure(sig: dict, prev: dict | None = None, today: date | None = None) -> dict:
    """signals → exposure.yaml 구조(점수·처방·추세 포함)."""
    today = today or date.today()
    s = score(sig)
    hist = list((prev or {}).get("history", []) or [])
    if s is not None and (not hist or hist[-1].get("date") != str(today)):
        hist.append({"date": str(today), "score": s})
    hist = hist[-12:]                # 최근 12회만
    return {
        "generated_at": str(today),
        "score": s,
        "measured": measured_dims(sig),     # 측정/미측정 구분(정직성)
        "note": sig.get("measured_by") or sig.get("note"),
        "queries": sig.get("queries", []),
        "naver_queries": sig.get("naver_queries", []),
        "place": sig.get("place", {}),
        "blog_mentions": sig.get("blog_mentions"),
        "name_baseline": sig.get("name_baseline") or {},
        "actions": prescribe(sig),
        "keyword_plan": keyword_plan(sig),  # 발견 키워드 구체 입력안
        "history": hist,
    }


# ── 측정 수집기(브라우저/CLI) — 실행 환경에서만. 스캐폴드는 expose_collect.py 로 분리 ──
def measure(target: dict) -> dict:
    """AI(Claude CLI) + 네이버(스크랩) 측정 → signals. 실패해도 부분 결과 반환."""
    import expose_collect
    return expose_collect.collect(target)


def main() -> int:
    ap = argparse.ArgumentParser(description="발견 케어(AI·네이버 노출) 엔진")
    ap.add_argument("client_dir", help="clients/{slug} (target.yaml 또는 targets/{slug}.yaml 사용)")
    ap.add_argument("--measure", action="store_true", help="AI/네이버 실제 측정(브라우저·CLI 필요)")
    ap.add_argument("--show", action="store_true", help="네이버 검색 상위 결과를 함께 출력(검증용)")
    ap.add_argument("--place", action="store_true",
                    help="플레이스 리뷰·사진을 우리 vs 경쟁사 스크랩(온머신, 느림)")
    args = ap.parse_args()

    cdir = Path(args.client_dir)
    slug = cdir.name
    target_path = next((p for p in (cdir / "target.yaml", Path("targets") / f"{slug}.yaml") if p.exists()), None)
    if not target_path:
        print(f"✗ target 없음: {cdir/'target.yaml'} 또는 targets/{slug}.yaml")
        return 2
    target = yaml.safe_load(target_path.read_text(encoding="utf-8")) or {}

    exp_path = cdir / "exposure.yaml"
    prev = yaml.safe_load(exp_path.read_text(encoding="utf-8")) if exp_path.exists() else None

    if args.measure:
        if args.show:
            target["_show"] = True
        if args.place:
            target["_place"] = True
        sig = measure(target)
        mq = sig.get("queries", [])
        nq = sig.get("naver_queries", [])
        print(f"  · 측정 결과: AI 언급 {sum(1 for q in mq if q.get('ai_mentioned'))}/{len(mq)}"
              f" · 네이버 발견 {sum(1 for x in nq if x.get('naver_found'))}/{len(nq)}"
              f" ({sig.get('measured_by','')})")
    elif prev and prev.get("queries"):
        sig = prev                      # 기존 측정값으로 점수·처방만 재계산
    else:
        print("측정값이 없어요. --measure 로 AI/네이버를 측정하거나, exposure.yaml 에 signals 를 채우세요.")
        return 1

    exp = build_exposure(sig, prev=prev)
    exp_path.write_text(yaml.safe_dump(exp, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"✓ {slug}: 발견점수 {exp['score']} · 액션 {len(exp['actions'])}개 → {exp_path}")
    for a in exp["actions"]:
        print(f"  · [{a['area']}] {a['title']} ({a['effort']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
