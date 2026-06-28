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


def test_keyword_plan_gap_ok_and_skips_generic():
    sig = {
        "naver_queries": [
            {"q": "영등포 레이어드컷", "spec": "레이어드컷", "naver_rank": None,
             "top": ["위닛블랙", "바운스플로"]},
            {"q": "영등포 뿌리펌", "spec": "뿌리펌", "naver_rank": 2, "top": ["살롱톤"]},
            {"q": "영등포 미용실", "spec": "미용실", "naver_rank": None, "top": []},
        ],
        "place": {"styles": ["애쉬브라운", "뿌리펌"],
                  "competitors": [{"name": "위닛블랙", "styles": ["레이어드컷"]}]},
    }
    plans = expose.keyword_plan(sig)
    assert len(plans) == 2                       # '미용실'(범용)은 제외
    gap = next(p for p in plans if p["spec"] == "레이어드컷")
    assert gap["status"] == "gap" and gap["has_style"] is False and "위닛블랙" in gap["proof"]
    ok = next(p for p in plans if p["spec"] == "뿌리펌")
    assert ok["status"] == "ok" and ok["has_style"] is True


def test_designer_card_picks_one_gap_with_praise():
    sig = {
        "naver_queries": [
            {"q": "영등포 레이어드컷", "spec": "레이어드컷", "naver_rank": None, "top": ["위닛블랙"]},
            {"q": "영등포 뿌리펌", "spec": "뿌리펌", "naver_rank": None, "top": []},
        ],
        "place": {"reviews": 1791, "rating": 4.9, "styles": ["애쉬브라운"],
                  "competitors": [{"name": "위닛블랙", "styles": ["레이어드컷"]}]},
        "name_baseline": {"name_rank": 1},
    }
    c = expose.designer_card(sig)
    assert "레이어드컷" in c["ask"] and "레이어드컷" in c["do"]   # 첫 갭 하나만
    assert "1위" in c["good"] and "1,791" in c["good"]            # 칭찬으로 시작
    assert "1개 더" in c["footer"]                                 # 남은 갭 안내(2개 중 1개 처리)


def test_keyword_plan_low_when_ranked_but_below_top5():
    sig = {"naver_queries": [{"q": "영등포 레이어드컷", "spec": "레이어드컷",
                              "naver_rank": 8, "naver_found": True, "top": []}],
           "place": {"styles": ["레이어드컷"]}}
    p = expose.keyword_plan(sig)[0]
    assert p["status"] == "low" and "8위" in p["advice"]


def test_designer_card_low_rank_says_position_not_absent():
    sig = {"naver_queries": [{"q": "영등포 레이어드컷", "spec": "레이어드컷",
                              "naver_rank": 8, "naver_found": True, "top": []}],
           "place": {"styles": ["레이어드컷"], "reviews": 1791}, "name_baseline": {"name_rank": 1}}
    c = expose.designer_card(sig)
    assert "8위" in c["ask"] and "안 보여요" not in c["ask"]   # '안 떠요'가 아니라 '8위'로 정직하게


def test_designer_card_positive_when_no_gaps():
    sig = {"naver_queries": [{"q": "영등포 펌", "spec": "펌", "naver_rank": 1, "top": []}],
           "place": {"styles": ["펌"], "reviews": 100}}
    c = expose.designer_card(sig)
    assert "잘 되고 있어요" in c["greeting"]


def test_designer_card_none_without_signals():
    assert expose.designer_card({"naver_queries": []}) is None


def test_build_exposure_includes_keyword_plan():
    sig = _sig(ai=2, nv=2)
    sig["naver_queries"] = [{"q": "영등포 펌", "spec": "펌", "naver_rank": None, "top": []}]
    sig["place"]["styles"] = []
    exp = expose.build_exposure(sig, today=date(2026, 6, 28))
    assert exp["keyword_plan"] and exp["keyword_plan"][0]["spec"] == "펌"
