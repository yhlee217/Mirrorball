"""발견 케어 엔진 — 점수·처방·추세(결정적) 테스트."""

from datetime import date

import expose


def _sig(ai, nv, reviews=14, photos=8, comp=42, blog=1):
    qs = []
    for i in range(6):
        qs.append({"q": f"q{i}", "ai_mentioned": i < ai,
                   "naver_found": i < nv, "naver_rank": (i + 1) if i < nv else None})
    return {"queries": qs, "place": {"reviews": reviews, "photos": photos, "comp_reviews_median": comp},
            "blog_mentions": blog}


def test_score_monotonic_in_signals():
    low = expose.score(_sig(ai=0, nv=0, reviews=0, photos=0, blog=0))
    high = expose.score(_sig(ai=6, nv=6, reviews=60, photos=20, blog=5))
    assert 0 <= low < high <= 100
    assert high >= 90 and low <= 10


def test_prescribe_reviews_when_below_competitor():
    acts = expose.prescribe(_sig(ai=2, nv=3, reviews=14, comp=42))
    assert any(a["area"] == "review" and "28" in a["title"] for a in acts)   # 42-14=28건 목표


def test_prescribe_photos_when_few():
    acts = expose.prescribe(_sig(ai=2, nv=3, reviews=50, comp=40, photos=4))
    assert any(a["area"] == "place" for a in acts)


def test_prescribe_caps_at_three_and_sorted():
    acts = expose.prescribe(_sig(ai=0, nv=0, reviews=0, photos=0, blog=0))
    assert len(acts) <= 3
    assert [a["priority"] for a in acts] == sorted(a["priority"] for a in acts)


def test_build_exposure_appends_history_and_actions():
    prev = {"history": [{"date": "2026-06-01", "score": 30}]}
    exp = expose.build_exposure(_sig(ai=2, nv=4), prev=prev, today=date(2026, 6, 28))
    assert exp["score"] == expose.score(_sig(ai=2, nv=4))
    assert exp["history"][-1] == {"date": "2026-06-28", "score": exp["score"]}
    assert len(exp["history"]) == 2 and exp["actions"]


def test_build_exposure_no_dup_same_day():
    prev = {"history": [{"date": "2026-06-28", "score": 40}]}
    exp = expose.build_exposure(_sig(ai=3, nv=3), prev=prev, today=date(2026, 6, 28))
    assert len(exp["history"]) == 1   # 같은 날 재실행 → 중복 안 쌓임
