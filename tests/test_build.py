"""프로필 생성기 — validate / schema / core.render / build_one 단위 테스트.

네트워크·외부 의존 없음. mock data + tmp dist.
"""

import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import build  # noqa: E402
import core  # noqa: E402
import schema  # noqa: E402
import validate  # noqa: E402


def make_data(**over):
    data = {
        "slug": "test",
        "display_name": "Mina",
        "korean_name": "김 민 아",
        "role": "헤어디자이너",
        "salon": "살롱 강남",
        "instagram": "mina.hair",
        "photo_url": "",
        "booking_url": "",
        "specialties": [
            {"name": "컷", "desc": "기본 커트"},
            {"name": "펌", "desc": "볼륨 펌", "signature": True},
        ],
        "about": ["경력 10년"],
        "portfolio_labels": ["컷", "펌", "컬러", "단발"],
        "faq": [{"q": "질문1", "a": "답변1"}, {"q": "질문2", "a": "답변2"}],
        "knows_about": ["컷", "펌"],
        "address_locality": "강남구",
        "address_region": "서울",
        "location": {"address": "서울 강남구 [주소 입력]", "directions": "2번 출구"},
        "tagline": "첫 줄\n둘째 줄",
    }
    data.update(over)
    return data


# --- validate ---------------------------------------------------------------
def test_validate_missing_required_raises():
    bad = make_data()
    del bad["salon"]
    with pytest.raises(ValueError):
        validate.validate(bad)


def test_validate_empty_required_list_raises():
    with pytest.raises(ValueError):
        validate.validate(make_data(specialties=[]))


def test_validate_faq_item_missing_qa_raises():
    with pytest.raises(ValueError):
        validate.validate(make_data(faq=[{"q": "질문만"}]))


def test_validate_warns_placeholder_and_empty_urls():
    warnings = validate.validate(make_data())
    assert any("photo_url" in w for w in warnings)
    assert any("booking_url" in w for w in warnings)
    assert any("[주소 입력]" in w for w in warnings)  # placeholder 경고


def test_validate_no_warning_when_filled():
    data = make_data(
        photo_url="https://x/p.jpg",
        booking_url="https://booking.naver.com/x",
        location={"address": "서울 강남구 1-2", "directions": "2번 출구"},
    )
    assert validate.validate(data) == []


# --- core 파생 --------------------------------------------------------------
def test_make_title():
    assert core.make_title(make_data()) == "김민아 · Mina | 헤어디자이너 · 살롱 강남"


def test_make_description_josa():
    # knows_about ["컷","펌"] → "컷과 펌" (컷=받침 → 과)
    desc = core.make_description(make_data())
    assert desc == "컷과 펌. 살롱 강남 헤어디자이너 김민아(mina.hair)."


def test_make_description_josa_and_join():
    # 펌=받침 → 과
    assert core.make_description(make_data(knows_about=["뿌리펌", "컬러"])).startswith("뿌리펌과 컬러.")
    # 컬러=받침 없음 → 와
    assert core.make_description(make_data(knows_about=["컬러", "펌"])).startswith("컬러와 펌.")
    # 3개 이상 → '·'로 잇고 마지막 직전 단어로 과/와 결정
    assert core.make_description(make_data(knows_about=["컷", "펌", "컬러"])).startswith("컷·펌과 컬러.")


# --- schema -----------------------------------------------------------------
def test_person_ld():
    p = schema.person_ld(make_data())
    assert p["@type"] == "Person" and p["name"] == "김민아"
    assert p["alternateName"] == "mina.hair"
    assert p["worksFor"]["address"]["addressCountry"] == "KR"
    assert p["sameAs"] == ["https://instagram.com/mina.hair"]


def test_faq_ld():
    f = schema.faq_ld(make_data())
    assert f["@type"] == "FAQPage" and len(f["mainEntity"]) == 2
    assert f["mainEntity"][0]["acceptedAnswer"]["text"] == "답변1"


# --- core.render ------------------------------------------------------------
def test_render_fragments():
    html = core.render(make_data())
    assert '<div class="ava-ph">M</div>' in html          # 이니셜 플레이스홀더
    assert "<h1>Mina</h1>" in html
    assert '<div class="ko-name">김 민 아</div>' in html   # 공백 자간 보존
    assert "첫 줄<br>둘째 줄" in html                       # tagline 줄바꿈
    assert '<div class="name">펌 <span class="badge">signature</span></div>' in html
    assert '<div class="name">컷</div>' in html            # 배지 없음
    assert 'href="[예약 링크]"' in html                    # 빈 booking → 플레이스홀더
    assert 'href="https://instagram.com/mina.hair"' in html
    assert html.count('<div class="faq">') == 2


def test_render_gallery_rows():
    # 4개 라벨 → 3+1 두 행
    html = core.render(make_data())
    assert "<div>컷</div><div>펌</div><div>컬러</div>\n      <div>단발</div>" in html


def test_render_jsonld_valid():
    html = core.render(make_data())
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(blocks) == 2
    person, faq = json.loads(blocks[0]), json.loads(blocks[1])
    assert person["name"] == "김민아" and len(faq["mainEntity"]) == 2


def test_render_escapes_html():
    # 사용자 텍스트의 특수문자는 이스케이프 (autoescape)
    html = core.render(make_data(about=["A & B <tag>"]))
    assert "A &amp; B &lt;tag&gt;" in html


# --- build_one (tmp dist) ---------------------------------------------------
def test_build_one_writes_and_validates(tmp_path):
    import yaml

    p = tmp_path / "mina.yaml"
    p.write_text(yaml.safe_dump(make_data(slug="mina"), allow_unicode=True), encoding="utf-8")
    res = build.build_one(str(p), dist=str(tmp_path / "dist"))
    out = tmp_path / "dist" / "mina" / "index.html"
    assert out.exists() and res["slug"] == "mina"
    # 빌드된 JSON-LD 가 유효한지 (build.check_jsonld 도 통과했음)
    assert build.check_jsonld(out.read_text(encoding="utf-8")) == 2


# --- 메뉴판 (2순위) ---------------------------------------------------------
def test_menu_section_renders_when_present():
    html = core.render(make_data(menu=[
        {"name": "커트", "desc": "디자인 커트", "price": "3만원", "time": "약 50분"},
        {"name": "펌", "price": "12만원~", "signature": True},
    ]))
    assert '<div class="eyebrow">Menu</div>' in html and "시술 안내" in html
    assert html.count('class="menu-item"') == 2
    assert '<div class="p">3만원</div>' in html
    assert "약 50분" in html
    assert '펌 <span class="badge">signature</span>' in html  # 메뉴 signature 배지
    assert ".menu-item{display:flex" in html  # 메뉴 CSS 주입


def test_no_menu_section_when_absent():
    html = core.render(make_data())  # menu 없음
    assert "시술 안내" not in html
    assert 'class="menu-item"' not in html
    assert ".menu-item{display:flex" not in html  # CSS 도 안 들어감


def test_validate_menu_requires_name_price():
    with pytest.raises(ValueError):
        validate.validate(make_data(menu=[{"name": "커트"}]))  # price 누락


# --- Before/After 갤러리 (1순위) --------------------------------------------
PORTFOLIO = [
    {"before": "https://x/b1.jpg", "after": "https://x/a1.jpg", "caption": "단발"},
    {"before": "https://x/b2.jpg", "after": "https://x/a2.jpg"},
]


def test_portfolio_gallery_renders_when_present():
    html = core.render(make_data(portfolio=PORTFOLIO))
    assert html.count('class="ba-item"') == 2
    assert 'class="ba-range"' in html
    assert 'src="https://x/a1.jpg"' in html and 'src="https://x/b1.jpg"' in html
    assert "<figcaption>단발</figcaption>" in html  # 캡션 있는 것
    assert "querySelectorAll('.ba-range')" in html  # 슬라이더 JS 주입
    assert ".ba-before{clip-path" in html  # 갤러리 CSS 주입
    assert 'class="gal"' not in html  # 라벨 폴백은 안 나옴


def test_portfolio_fallback_label_grid_when_absent():
    html = core.render(make_data())  # portfolio 없음
    assert 'class="ba-gal"' not in html
    assert ".ba-before{clip-path" not in html
    assert "querySelectorAll('.ba-range')" not in html  # JS 도 안 들어감
    assert 'class="gal"' in html  # 기존 라벨 그리드 유지
    assert "발행 시 인스타 대표 작업 사진으로 교체" in html  # 기존 안내문 유지


def test_validate_portfolio_requires_before_after():
    with pytest.raises(ValueError):
        validate.validate(make_data(portfolio=[{"before": "https://x/b.jpg"}]))  # after 누락


# --- 후기 위젯 -------------------------------------------------------------
REVIEWS = [
    {"stars": 5, "text": "최고예요", "by": "김○○", "service": "커트"},
    {"stars": 4, "text": "만족합니다", "by": "이○○"},
]


def test_reviews_render_with_avg():
    html = core.render(make_data(reviews=REVIEWS))
    assert '<div class="eyebrow">Reviews</div>' in html and "고객 후기" in html
    assert html.count('class="review"') == 2
    assert '<div class="rev-score">4.5</div>' in html  # (5+4)/2
    assert "후기 2건" in html
    assert "★★★★★" in html and "★★★★☆" in html  # 5점/4점
    assert "김○○ · 커트" in html
    assert ".rev-score{font-family" in html  # 후기 CSS 주입


def test_no_reviews_when_absent():
    html = core.render(make_data())
    assert "고객 후기" not in html
    assert 'class="review"' not in html
    assert ".rev-score{font-family" not in html


def test_validate_reviews_stars_range():
    with pytest.raises(ValueError):
        validate.validate(make_data(reviews=[{"text": "x", "by": "y", "stars": 6}]))
    with pytest.raises(ValueError):
        validate.validate(make_data(reviews=[{"text": "x", "by": "y"}]))  # stars 누락


# --- 스타일 찾기 진단 -------------------------------------------------------
QUIZ = {
    "intro": "한 가지만 답하세요",
    "questions": [
        {"q": "얼굴형은?", "options": [
            {"label": "계란형", "style": "layered"},
            {"label": "둥근형", "style": "perm"},
        ]},
    ],
    "results": {
        "layered": {"title": "레이어드컷", "desc": "자연스러운 흐름", "cta_label": "상담받기"},
        "perm": {"title": "디지털펌", "desc": "볼륨", "cta_label": "상담받기"},
    },
}


def test_style_quiz_renders_when_present():
    import json
    import re

    html = core.render(make_data(style_quiz=QUIZ, booking_url="https://book/x"))
    assert "어울리는 스타일 찾기" in html and 'id="style-quiz"' in html
    assert ".quiz-opt{border" in html          # CSS 주입
    assert "getElementById('style-quiz')" in html  # JS 주입
    blob = re.search(r'id="quiz-data">(.*?)</script>', html, re.S).group(1)
    q = json.loads(blob)
    assert len(q["questions"]) == 1 and q["booking"] == "https://book/x"  # 예약링크 주입


def test_no_style_quiz_when_absent():
    html = core.render(make_data())
    assert "어울리는 스타일 찾기" not in html
    assert ".quiz-opt{border" not in html
    assert "getElementById('style-quiz')" not in html


def test_validate_quiz_missing_result_for_style():
    bad = dict(QUIZ)
    bad = {**QUIZ, "results": {"layered": {"title": "레이어드컷"}}}  # perm 결과 없음
    with pytest.raises(ValueError):
        validate.validate(make_data(style_quiz=bad))


def test_validate_quiz_requires_questions_and_results():
    with pytest.raises(ValueError):
        validate.validate(make_data(style_quiz={"questions": []}))


# --- SEO (OG 메타 / sitemap / robots) --------------------------------------
def test_og_meta_tags():
    html = core.render(make_data(photo_url="https://x/p.jpg", site_url="https://x.site"))
    assert '<meta property="og:title"' in html
    assert '<meta property="og:description"' in html
    assert '<meta name="twitter:card" content="summary">' in html
    assert '<meta property="og:image" content="https://x/p.jpg">' in html
    assert '<meta property="og:url" content="https://x.site">' in html


def test_og_image_absent_without_photo():
    html = core.render(make_data())  # photo 없음
    assert "og:image" not in html
    assert "og:url" not in html  # site_url 없음


def test_write_site_files(tmp_path):
    built = [
        {"slug": "a", "site_url": "https://a.site"},
        {"slug": "b", "site_url": ""},  # site_url 없는 디자이너
    ]
    written = build.write_site_files(built, dist=str(tmp_path))
    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://a.site" in sitemap and "https://b" not in sitemap
    assert "Sitemap: https://a.site/sitemap.xml" in robots


def test_robots_without_any_site_url(tmp_path):
    build.write_site_files([{"slug": "a", "site_url": ""}], dist=str(tmp_path))
    assert (tmp_path / "robots.txt").exists()
    assert not (tmp_path / "sitemap.xml").exists()  # url 없으면 sitemap 없음


def test_build_one_real_hayewoni(tmp_path):
    # 실제 예시 파일도 빌드되고 경고 3개(photo/booking/주소)
    res = build.build_one("designers/hayewoni.yaml", dist=str(tmp_path / "dist"))
    assert res["slug"] == "hayewoni"
    assert (tmp_path / "dist" / "hayewoni" / "index.html").exists()
    assert len(res["warnings"]) == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
