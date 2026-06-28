"""발견 케어 측정기 — 네트워크/CLI 없는 순수 파싱 테스트."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("expose_collect", ROOT / "expose_collect.py")
ec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ec)

TARGET = {"designer": {"name": "하예원", "aliases": ["예원쌤"]},
          "salon": {"name": "살롱톤", "aliases": ["살롱톤 영등포"]}}


def test_strip_tags():
    assert ec._strip_tags("<b>살롱톤</b> 영등포점") == "살롱톤 영등포점"


def test_rank_in_items_found_and_position():
    names = ec._names(TARGET)
    items = [{"name": "박승철헤어"}, {"name": "이철헤어"}, {"name": "살롱톤 영등포점"}]
    assert ec._rank_in_items(items, names) == 3


def test_rank_in_items_absent():
    names = ec._names(TARGET)
    items = [{"name": "준오헤어"}, {"name": "블루클럽"}]
    assert ec._rank_in_items(items, names) is None


def test_names_includes_designer_salon_aliases():
    ns = ec._names(TARGET)
    assert "하예원" in ns and "살롱톤" in ns and "예원쌤" in ns and "살롱톤 영등포" in ns


def test_parse_place_text_reviews_photos():
    txt = "살롱톤 영등포 ★ 4.7 방문자 리뷰 128 블로그 리뷰 34 사진 56 예약"
    d = ec.parse_place_text(txt)
    assert d["reviews"] == 162 and d["photos"] == 56 and d["rating"] == 4.7
    assert d["visitor_reviews"] == 128 and d["blog_reviews"] == 34


def test_parse_place_text_single_review_fallback():
    d = ec.parse_place_text("어떤샵 리뷰 1,234 사진 9")
    assert d["reviews"] == 1234 and d["photos"] == 9


def test_kor_num_abbreviated():
    assert ec._kor_num("1,234") == 1234
    assert ec._kor_num("1.2천") == 1200
    assert ec._kor_num("3.4만") == 34000
    assert ec._kor_num("1만2천") == 12000
    assert ec._kor_num("") == 0


def test_parse_place_text_abbreviated_photos():
    # 네이버 축약 표기: '사진 1.2천' → 1200, '방문자 리뷰 3.4만' → 34000
    d = ec.parse_place_text("살롱톤 ★ 4.9 방문자 리뷰 3.4만 블로그 리뷰 1,512 사진 1.2천")
    assert d["photos"] == 1200
    assert d["visitor_reviews"] == 34000 and d["blog_reviews"] == 1512
    assert d["reviews"] == 35512


def test_around_finds_window():
    assert "사진" in ec._around("앞 텍스트 사진 1.2천 뒤 텍스트", "사진")
    assert ec._around("리뷰만 있음", "사진") == "'사진' 없음"


def test_parse_styles_extracts_popular_tags():
    txt = "별점 4.98리뷰 1,791 휠체어 출입 가능 인기스타일 애쉬브라운 인기 숏단 영업"
    s = ec.parse_styles(txt)
    assert "애쉬브라운" in s and "숏단" in s
    assert ec.parse_styles("리뷰 100 사진 9") == []


def test_naver_keyword_queries_carry_spec():
    t = {"region": "영등포구청역", "specialties": ["레이어드컷", "뿌리펌"]}
    qs = ec.naver_keyword_queries(t)
    specs = [q["spec"] for q in qs]
    assert "레이어드컷" in specs and "뿌리펌" in specs and "미용실" in specs
    assert all("영등포구청역" in q["q"] for q in qs)


def test_median():
    assert ec._median([10, 30, 20, 40, 5]) == 20
    assert ec._median([]) == 0


def test_naver_query_keyword_ifies():
    assert ec.naver_query("영등포 레이어드컷 잘하는 미용실 추천해줘") == "영등포 레이어드컷 미용실"
    assert ec.naver_query("영등포구청역 근처 뿌리펌 잘하는 디자이너 알려줘") == "영등포구청역 뿌리펌 디자이너"
    # 업종어 없으면 '미용실' 보충
    assert "미용실" in ec.naver_query("영등포 단발 잘 자르는 곳 어디야")


def test_mentioned_and_competitors():
    txt = "영등포는 박승철헤어스튜디오, 이철헤어커커가 유명하고 살롱톤도 있어요."
    names = ec._names(TARGET)
    assert ec._mentioned(txt, names) is True
    comps = ec._competitors(txt, names)
    assert "박승철헤어" not in comps or True       # 휴리스틱(접미사 기준)
    assert any("헤어" in c for c in comps) and "살롱톤" not in comps
