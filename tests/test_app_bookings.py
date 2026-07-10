"""app mergeBookings — 서버 예약 + 로컬 예약 병합 회귀 테스트.

핵심 회귀: 빌드가 실어준 예약(bookings.yaml→resolve_bookings; HandSOS/네이버 수집분)을
앱 derive 가 떨어뜨리지 않아야 한다(이전엔 CUSTS 로만 재구성해 서버 예약을 잃었음).
오늘 이후만, (이름|날짜|시간) 중복 제거, 날짜·시간순 정렬.

index.html 의 순수 함수 소스를 마커로 추출해 실제 브라우저에서 평가(test_app_merge 와 동일 방식,
playwright 없으면 skip).
"""

import re
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "app" / "index.html"


def _extract():
    src = INDEX.read_text(encoding="utf-8")
    m = re.search(r"//\s*<mergeBookings>(.*?)//\s*</mergeBookings>", src, re.S)
    assert m, "index.html 에서 mergeBookings 마커를 찾지 못함"
    assert "function mergeBookings" in m.group(1)
    return m.group(1)


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium 실행 불가: {exc}")
        pg = b.new_page()
        pg.set_content("<!doctype html><html><body></body></html>")
        pg.add_script_tag(content=_extract())
        yield pg
        b.close()


def _merge(page, server, local, ts):
    return page.evaluate("(a)=>mergeBookings(a[0], a[1], a[2])", [server, local, ts])


def test_server_bookings_kept(page):
    # 서버 예약(HandSOS 수집분)이 유지되어야 — 핵심 회귀(앱에 '다가오는 예약' 표시)
    server = [{"name": "강유신", "service": "남자컷", "time": "19:30", "date": "2026-07-12", "id": "c1"}]
    out = _merge(page, server, [], "2026-07-10")
    assert len(out) == 1
    assert out[0]["name"] == "강유신" and out[0]["id"] == "c1" and out[0]["time"] == "19:30"


def test_merge_and_dedupe(page):
    server = [{"name": "A", "service": "컷", "time": "10:00", "date": "2026-07-11", "id": "c1"}]
    local = [{"name": "A", "service": "컷", "time": "10:00", "date": "2026-07-11", "id": "c1"},   # dup
             {"name": "B", "service": "펌", "time": "14:00", "date": "2026-07-11", "id": "c2"}]
    out = _merge(page, server, local, "2026-07-10")
    assert [b["name"] for b in out] == ["A", "B"]            # 중복 1개로, 로컬 예약도 합침


def test_past_dropped(page):
    server = [{"name": "어제", "time": "10:00", "date": "2026-07-05", "id": "c1"},
              {"name": "내일", "time": "10:00", "date": "2026-07-11", "id": "c2"}]
    out = _merge(page, server, [], "2026-07-10")
    assert [b["name"] for b in out] == ["내일"]              # 오늘 이전 제외


def test_sorted_by_datetime(page):
    server = [{"name": "늦", "time": "18:00", "date": "2026-07-12", "id": "c1"},
              {"name": "이른", "time": "09:00", "date": "2026-07-11", "id": "c2"}]
    out = _merge(page, server, [], "2026-07-10")
    assert [b["name"] for b in out] == ["이른", "늦"]
