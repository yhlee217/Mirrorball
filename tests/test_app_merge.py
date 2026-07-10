"""app/index.html 의 mergeCustomers 회귀 테스트 — 빌드 시드 + 로컬 편집 병합(id=c{custno} 기준).

일관성 계약을 고정한다:
  · 거래 필드(이력·매출)는 새 빌드(HandSOS)가 최신으로 반영된다.
  · 디자이너의 로컬 수동 편집(생일·메모·취향 등)은 보존된다.
  · 앱에서 추가한 로컬 전용 고객은 유지된다.
  · 빈 로컬 수동값이 빌드 값을 지우지 않는다.

index.html 안의 순수 함수 소스를 마커로 추출해 실제 브라우저에서 평가한다
(test_harvest_js.py 와 동일한 방식 — playwright 없으면 skip).
"""

import re
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "app" / "index.html"


def _extract_merge() -> str:
    src = INDEX.read_text(encoding="utf-8")
    m = re.search(r"//\s*<mergeCustomers>(.*?)//\s*</mergeCustomers>", src, re.S)
    assert m, "index.html 에서 mergeCustomers 마커를 찾지 못함"
    body = m.group(1)
    assert "function mergeCustomers" in body, "추출 구간에 mergeCustomers 정의가 없음"
    return body


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:                     # 브라우저 미탑재 환경
            pytest.skip(f"chromium 실행 불가: {exc}")
        pg = b.new_page()
        pg.set_content("<!doctype html><html><body></body></html>")
        pg.add_script_tag(content=_extract_merge())
        yield pg
        b.close()


def _merge(page, seed, local):
    return page.evaluate("(a)=>mergeCustomers(a[0], a[1])", [seed, local])


def test_new_build_visit_reaches_edited_customer(page):
    # 디자이너가 생일을 넣은 고객에게도 새 빌드의 방문/매출이 반영되어야(다운스트림 일관성)
    seed = [{"id": "c5120", "name": "배상웅", "custno": "5120",
             "history": [{"date": "2026-06-26", "service": "컷"},
                         {"date": "2026-07-01", "service": "펌"}], "total_won": 120000}]
    local = [{"id": "c5120", "name": "배상웅", "custno": "5120", "birthday": "06-26",
              "history": [{"date": "2026-06-26", "service": "컷"}], "total_won": 28000}]
    out = _merge(page, seed, local)
    assert len(out) == 1
    c = out[0]
    assert len(c["history"]) == 2         # 새 빌드 이력 반영
    assert c["total_won"] == 120000       # 거래 필드는 빌드가 최신
    assert c["birthday"] == "06-26"       # 디자이너 수동 입력 보존


def test_local_only_customer_kept(page):
    seed = [{"id": "c1", "name": "A", "custno": "1"}]
    local = [{"id": "c1", "name": "A", "custno": "1"},
             {"id": "u_added", "name": "신규", "birthday": "03-03"}]
    out = _merge(page, seed, local)
    assert sorted(c["id"] for c in out) == ["c1", "u_added"]   # 앱에서 추가한 고객 보존


def test_new_handsos_customer_included_and_edit_preserved(page):
    seed = [{"id": "c1", "name": "A", "custno": "1"},
            {"id": "c2", "name": "B", "custno": "2"}]           # c2 = 새 HandSOS 고객
    local = [{"id": "c1", "name": "A", "custno": "1", "memo": "단골"}]
    out = _merge(page, seed, local)
    assert sorted(c["id"] for c in out) == ["c1", "c2"]         # 신규 고객 포함
    c1 = next(c for c in out if c["id"] == "c1")
    assert c1["memo"] == "단골"                                  # 기존 편집 보존


def test_empty_local_manual_does_not_wipe_build(page):
    seed = [{"id": "c1", "name": "A", "custno": "1", "birthday": "12-25"}]
    local = [{"id": "c1", "name": "A", "custno": "1", "birthday": ""}]
    out = _merge(page, seed, local)
    assert out[0]["birthday"] == "12-25"       # 빈 로컬값이 빌드값을 지우지 않음


def test_manual_edit_wins_over_build(page):
    # 같은 수동필드가 양쪽에 있으면 로컬(디자이너 편집)이 우선
    seed = [{"id": "c1", "name": "A", "custno": "1", "memo": "빌드메모"}]
    local = [{"id": "c1", "name": "A", "custno": "1", "memo": "디자이너메모"}]
    out = _merge(page, seed, local)
    assert out[0]["memo"] == "디자이너메모"


def test_first_boot_no_local_equals_seed(page):
    seed = [{"id": "c1", "name": "A", "custno": "1", "birthday": "01-01"}]
    assert _merge(page, seed, []) == seed
