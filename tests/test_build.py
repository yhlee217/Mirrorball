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


def test_build_one_real_hayewoni(tmp_path):
    # 실제 예시 파일도 빌드되고 경고 3개(photo/booking/주소)
    res = build.build_one("designers/hayewoni.yaml", dist=str(tmp_path / "dist"))
    assert res["slug"] == "hayewoni"
    assert (tmp_path / "dist" / "hayewoni" / "index.html").exists()
    assert len(res["warnings"]) == 3


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
