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
    last = exp["history"][-1]
    assert last["date"] == "2026-06-28" and last["score"] == exp["score"] and last["ai"] == 2
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


def test_kakao_message_renders_card_for_relay():
    card = {"greeting": "이번 주 딱 하나만요 🙏", "good": "레이어드펌 4위",
            "ask": "손님이 '영등포시장역 뿌리펌' 검색하면 안 보여요.",
            "do": "스마트플레이스 스타일에 '뿌리펌'을 등록해 주세요.",
            "footer": "나머지는 제가 챙길게요"}
    msg = expose.kakao_message(card, "하예원")
    assert msg.startswith("하예원님") and "뿌리펌" in msg and "→ " in msg
    assert "레이어드펌 4위" in msg
    assert expose.kakao_message(None) == ""


def test_ai_footprint_plan_uses_strong_keyword_and_name():
    sig = {
        "queries": [{"q": "q1", "ai_mentioned": False}, {"q": "q2", "ai_mentioned": False}],
        "identity": {"designer": "하예원", "salon": "살롱톤", "region": "영등포시장역"},
        "naver_queries": [
            {"q": "영등포시장역 레이어드펌", "spec": "레이어드펌", "naver_rank": 4, "top": []},
            {"q": "영등포시장역 뿌리펌", "spec": "뿌리펌", "naver_rank": None, "top": []},
        ],
        "place": {"styles": []},
    }
    ap = expose.ai_footprint_plan(sig)
    assert ap["ai_mentions"] == 0 and ap["push_keyword"] == "레이어드펌"   # 이미 강한 4위 시술로
    assert any("하예원" in a["title"] and "영등포시장역" in a["title"] for a in ap["actions"])


def test_ai_footprint_plan_quiet_when_ai_already_cites():
    sig = {"queries": [{"q": "q1", "ai_mentioned": True}],
           "identity": {"designer": "하예원", "region": "영등포시장역"},
           "naver_queries": [], "place": {}}
    assert expose.ai_footprint_plan(sig)["actions"] == []     # 충분히 언급되면 안 흔듦


def test_franchise_ratio_and_hard_flag():
    assert expose._franchise_ratio(["차홍룸 여의도점", "준오헤어 IFC", "박승철헤어"]) == 1.0
    assert expose._franchise_ratio(["에이저헤어", "더엔느헤어", "제오헤어"]) == 0.0
    sig = {"naver_queries": [
        {"q": "여의도 레이어드컷", "spec": "레이어드컷", "region": "여의도", "naver_rank": None,
         "top": ["차홍룸 여의도점", "준오헤어 여의도점", "박승철헤어스투디오"]},
    ], "place": {"styles": []}}
    p = expose.keyword_plan(sig)[0]
    assert p["hard"] is True and "프랜차이즈" in p["advice"]


def test_designer_card_weekly_focus_primary_region_only():
    # 주간 '딱 하나'와 'N개 더'는 실제 위치(primary) 동네만 — 멀거나 승산 낮은 옆 동네는 제외
    def kw(q, spec, region, rank):
        return {"q": q, "spec": spec, "region": region, "naver_rank": rank,
                "naver_found": rank is not None, "top": []}
    sig = {"queries": [{"q": "q", "ai_mentioned": False}],
           "identity": {"designer": "하예원", "region": "영등포시장역"},
           "naver_queries": [
               kw("영등포시장역 뿌리펌", "뿌리펌", "영등포시장역", None),
               kw("영등포시장역 레이어드컷", "레이어드컷", "영등포시장역", 6),
               kw("영등포구청역 뿌리펌", "뿌리펌", "영등포구청역", None),   # 옆 동네 — 제외
               kw("신길역 뿌리펌", "뿌리펌", "신길역", None),               # 옆 동네 — 제외
           ], "place": {"styles": []}}
    c = expose.designer_card(sig)
    assert "영등포시장역 뿌리펌" in c["ask"]
    assert "1개 더" in c["footer"]    # primary 동네 todo 2개(뿌리펌·레이어드컷) → 남은 1개


def test_designer_card_deprioritizes_franchise_region():
    sig = {"naver_queries": [
        {"q": "여의도 레이어드컷", "spec": "레이어드컷", "region": "여의도", "naver_rank": None,
         "top": ["차홍룸 여의도점", "준오헤어 여의도점", "박승철헤어스투디오"]},
        {"q": "영등포시장역 뿌리펌", "spec": "뿌리펌", "region": "영등포시장역", "naver_rank": None,
         "top": ["제오헤어 영등포시장역점", "소요 영등포점"]},
    ], "place": {"styles": []}}
    c = expose.designer_card(sig)
    assert "뿌리펌" in c["do"] and "여의도" not in c["ask"]   # 승산 있는 동네부터, 여의도는 뒤로


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
