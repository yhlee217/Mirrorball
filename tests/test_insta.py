"""인스타 발견 지표 엔진 — 점유율·점수·트렌드·추세(결정적) 테스트."""

from datetime import date

import insta


def _sig(our_brand=30, our_eng=120, comp=((20, 100), (10, 80)), mentions=5):
    comps = [{"username": f"c{i}", "brand_count": b, "engagement": e, "measured": True}
             for i, (b, e) in enumerate(comp)]
    return {"measured": True,
            "our": {"username": "salontone", "brand_count": our_brand,
                    "engagement": our_eng, "mentions": mentions},
            "competitors": comps,
            "hashtags": [{"tag": "영등포레이어드컷", "count": 40, "engagement": 90}]}


def test_share_of_voice():
    sov, cov = insta.share_of_voice(_sig(our_brand=30, comp=((20, 100), (10, 80))))
    assert round(sov, 2) == 0.5 and cov == 2          # 30 / (30+20+10)
    assert insta.share_of_voice({"our": {"brand_count": None}, "competitors": []}) == (None, 0)


def test_score_monotonic():
    low = insta.score(_sig(our_brand=2, our_eng=20, comp=((50, 200), (40, 180)), mentions=0))
    high = insta.score(_sig(our_brand=80, our_eng=400, comp=((10, 50), (5, 40)), mentions=10))
    assert 0 <= low < high <= 100


def test_measured_dims_honest_about_personal_competitors():
    # 경쟁사 전부 미측정(개인계정) → sov/engage 차원이 빠진다
    sig = {"measured": True, "our": {"brand_count": 30, "engagement": 120, "mentions": 3},
           "competitors": [{"username": "c1", "measured": False}]}
    m = insta.measured_dims(sig)
    assert m["sov"] is False and m["engage"] is False and m["presence"] is True
    assert insta.score(sig) is not None               # presence 만으로도 점수는 나옴


def test_hashtag_trends_sorts_by_growth():
    prev = {"hashtags": [{"tag": "레이어드펌", "count": 30}, {"tag": "뿌리펌", "count": 50}]}
    sig = {"hashtags": [{"tag": "레이어드펌", "count": 45}, {"tag": "뿌리펌", "count": 48}]}
    tr = insta.hashtag_trends(sig, prev)
    assert tr[0]["tag"] == "레이어드펌" and tr[0]["delta"] == 15   # 가장 빨리 큰 게 먼저


def test_insta_changes_and_build_history():
    prev = {"history": [{"date": "2026-06-14", "score": 30, "sov": 0.40, "brand_count": 20}]}
    sig = _sig(our_brand=30, comp=((20, 100), (10, 80)))   # sov 0.5
    ch = insta.insta_changes(sig, prev, today=date(2026, 6, 28))
    assert ch["sov_prev"] == 0.40 and ch["sov"] == 0.5 and ch["weeks"] == 2
    assert ch["brand_delta"] == 10
    exp = insta.build_insta(sig, prev=prev, today=date(2026, 6, 28))
    assert exp["history"][-1]["sov"] == 0.5 and exp["sov_coverage"] == 2
