"""인스타 수집기 — 네트워크 없는 순수 파싱 테스트(샘플 JSON)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("insta_collect", ROOT / "insta_collect.py")
ic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ic)


def test_eng_list_and_avg():
    media = [{"like_count": 100, "comments_count": 5}, {"like_count": 50, "comments_count": 0}, None]
    assert ic._eng_list(media) == [105, 50]
    assert ic._avg([105, 50]) == 77.5
    assert ic._avg([]) is None


def test_parse_account():
    js = {"username": "salontone", "followers_count": 1200, "media_count": 340,
          "media": {"data": [{"like_count": 80, "comments_count": 4},
                             {"like_count": 120, "comments_count": 6}]}}
    a = ic.parse_account(js)
    assert a["username"] == "salontone" and a["followers"] == 1200
    assert a["posts"] == 2 and a["engagement"] == 105.0


def test_parse_business_discovery_present_and_absent():
    js = {"business_discovery": {"username": "rivalhair", "followers_count": 5000,
          "media_count": 900, "media": {"data": [{"like_count": 200, "comments_count": 10}]}}}
    bd = ic.parse_business_discovery(js)
    assert bd["measured"] is True and bd["followers"] == 5000 and bd["engagement"] == 210.0
    assert ic.parse_business_discovery({}) is None        # 개인/비공개 → None


def test_parse_hashtag_media_sample_count():
    js = {"data": [{"like_count": 10, "comments_count": 1},
                   {"like_count": 20, "comments_count": 0},
                   {"like_count": 30, "comments_count": 5}]}
    d = ic.parse_hashtag_media(js)
    assert d["count"] == 3 and d["engagement"] == round((11 + 20 + 35) / 3, 1)


def test_collect_no_keys_returns_unmeasured():
    out = ic.collect({})        # secrets 없을 때(키 없음) — 빈 신호
    assert out.get("measured") is False or "our" in out   # 키 있으면 our, 없으면 measured False
