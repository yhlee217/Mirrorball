"""app 소개 편집 — profileFromForm(순수 병합, 필터 없음) + cleanProfile(빈행 제거) + 스모크.

profileFromForm: 폼값 → 프로필 병합. 시술(name·desc·대표)·포트폴리오·소개·FAQ·연락처 갱신,
영문(en)·slug·위치 등 구조 보존, 편집 중이라 빈 행은 유지(트림만). cleanProfile 이 저장·발행 전
빈 행 제거. 스모크: 전체 index.html 로드 시 JS 오류 없어야(큰 편집 회귀 차단). playwright 없으면 skip.
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "app" / "index.html"


def _extract():
    m = re.search(r"//\s*<profileform>(.*?)//\s*</profileform>", INDEX.read_text(encoding="utf-8"), re.S)
    assert m, "index.html 에서 <profileform> 마커를 찾지 못함"
    assert "function profileFromForm" in m.group(1) and "function cleanProfile" in m.group(1)
    return m.group(1)


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium 실행 불가: {exc}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser):
    pg = browser.new_page()
    pg.set_content("<!doctype html><html><body></body></html>")
    pg.add_script_tag(content=_extract())
    return pg


BASE = {
    "slug": "hayewoni", "display_name": "Hayewoni", "tagline": "old",
    "about": ["a1", "a2"],
    "specialties": [{"name": "레이어드컷", "desc": "d1"},
                    {"name": "컨설팅", "desc": "d2", "signature": True}],
    "portfolio_labels": ["레이어드컷", "뿌리펌"],
    "faq": [{"q": "q1", "a": "a1"}],
    "booking_url": "https://old", "instagram": "old_ig",
    "en": {"tagline": "EN"},
}


def _merge(page, base, vals):
    return page.evaluate("(a)=>profileFromForm(a[0],a[1])", [base, vals])


def _clean(page, p):
    return page.evaluate("(x)=>cleanProfile(x)", p)


def test_updates_tagline_and_links(page):
    out = _merge(page, BASE, {"tagline": "새", "booking_url": "https://new", "instagram": "new_ig"})
    assert out["tagline"] == "새"
    assert out["booking_url"] == "https://new"
    assert out["instagram"] == "new_ig"


def test_preserves_en_and_slug(page):
    out = _merge(page, BASE, {"tagline": "새"})
    assert out["slug"] == "hayewoni"
    assert out["en"] == {"tagline": "EN"}                       # 영문 보존


def test_specialties_full_edit(page):
    vals = {"specialties": [{"name": "레이어드컷", "desc": "새d1", "signature": False},
                            {"name": "새시술", "desc": "새설명", "signature": True}]}
    out = _merge(page, BASE, vals)
    assert out["specialties"][0] == {"name": "레이어드컷", "desc": "새d1"}   # signature False → 키 없음
    assert out["specialties"][1] == {"name": "새시술", "desc": "새설명", "signature": True}


def test_signature_toggle_off_removes_key(page):
    out = _merge(page, BASE, {"specialties": [{"name": "x", "desc": "y", "signature": False}]})
    assert "signature" not in out["specialties"][0]


def test_portfolio_labels_edit(page):
    out = _merge(page, BASE, {"portfolio_labels": ["단발", "컬러"]})
    assert out["portfolio_labels"] == ["단발", "컬러"]


def test_profileFromForm_trims_but_keeps_blanks(page):
    out = _merge(page, BASE, {"about": ["x", "  ", ""]})
    assert out["about"] == ["x", "", ""]                        # 트림만, 필터 없음(편집 중 빈 행 유지)


def test_cleanProfile_filters_empties(page):
    p = _merge(page, BASE, {"about": ["x", "", "  "],
                            "faq": [{"q": "Q", "a": ""}, {"q": "", "a": ""}],
                            "specialties": [{"name": "s", "desc": ""}, {"name": "", "desc": ""}],
                            "portfolio_labels": ["a", ""]})
    c = _clean(page, p)
    assert c["about"] == ["x"]
    assert c["faq"] == [{"q": "Q", "a": ""}]
    assert [s["name"] for s in c["specialties"]] == ["s"]
    assert c["portfolio_labels"] == ["a"]


def test_base_not_mutated(page):
    r = page.evaluate("()=>{var b={tagline:'old',about:['a']};"
                      "profileFromForm(b,{tagline:'새',about:['x']});"
                      "return b.tagline+'|'+b.about.join(',');}")
    assert r == "old|a"                                          # JS 원본 dict 불변


def test_index_loads_without_js_errors(browser):
    # 전체 index.html 로드 → 구문/런타임 오류 없어야(큰 편집 회귀 차단). 데이터 fetch 는 실패→boot(null).
    errors = []
    pg = browser.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.set_content(INDEX.read_text(encoding="utf-8"))
    pg.wait_for_timeout(400)
    pg.close()
    assert not errors, "index.html JS 오류: " + "; ".join(errors)
