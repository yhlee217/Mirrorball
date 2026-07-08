"""handsos_harvest.js 회귀 테스트 — 합성 핸드SOS DOM 을 실제 브라우저에서 수확.

지금까지 0% 커버리지였던 수확 JS(테이블 탐색·숨김 툴팁 추출·연속행 승계·gotoP 페이징·
총건수 파싱)를 픽스처로 고정한다. 핸드SOS UI 를 흉내낸 구조가 바뀌는 게 아니라
'우리 JS 의 계약'이 바뀌는 걸 잡는 테스트.
"""

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
HARVEST_JS = ROOT / "scripts" / "handsos_harvest.js"

# 핸드SOS 매출상세목록 흉내: 2페이지(2행+1행), 숨김 툴팁(strCustomerInfo), 메모(saleStrMemoList),
# 상세메뉴 title 속성, 연속행(같은 방문 추가 시술), gotoP 페이징 + current 마커.
FIXTURE = """<!doctype html><html><body>
<div>총 3개</div>
<table id="list_tbl">
  <tr><th>날짜</th><th>고객명</th><th>상세메뉴</th><th>담당</th><th>결제액</th><th>메모</th></tr>
  <tbody id="tb">
  <tr>
    <td>26-06-26 19:41</td>
    <td>배상웅<span id="strCustomerInfo1" style="display:none">고객명 : 배상웅
전화 번호 : 010-1234-7305
고객 번호 : 0005120
이전방문 : 2026-05-29</span></td>
    <td title="남자컷(부원장)">남자컷</td><td>하예원</td><td>28,000</td>
    <td><span id="saleStrMemoList1">손상 신경 씀상세보기</span></td>
  </tr>
  <tr>
    <td></td><td></td>
    <td title="다운펌(부원장)">다운펌</td><td>하예원</td><td>91,000</td><td></td>
  </tr>
  </tbody>
</table>
<div id="pager"><a class="current" onclick="gotoP(1)">1</a> <a onclick="gotoP(2)">2</a></div>
<script>
  window.gotoP = function(n){
    if(n===2){
      document.getElementById('tb').innerHTML =
        '<tr><td>26-06-25 11:00</td>' +
        '<td>조희진<span id="strCustomerInfo2" style="display:none">고객명 : 조희진\\n전화 번호 : 010-0000-0218\\n고객 번호 : 0002767</span></td>' +
        '<td title="모발클리닉">모발클리닉</td><td>하예원</td><td>80,000</td><td></td></tr>';
      document.getElementById('pager').innerHTML = '<a onclick="gotoP(1)">1</a> <a class="current">2</a>';
    }
  };
</script>
</body></html>"""


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            exe = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
            if not exe.exists():
                pytest.skip("chromium 실행 불가(브라우저 없음)")
            b = p.chromium.launch(executable_path=str(exe))
        pg = b.new_page()
        yield pg
        b.close()


def _harvest(page, html: str) -> dict:
    page.set_content(html)
    page.add_script_tag(content=HARVEST_JS.read_text(encoding="utf-8"))
    return page.evaluate("__handsosHarvest({})")


def test_harvest_full_two_pages(page):
    r = _harvest(page, FIXTURE)
    assert r["error"] is None
    assert r["total"] == 3 and len(r["rows"]) == 3          # '총 3개' 대사 + 2페이지 수확

    r1, r2, r3 = r["rows"]
    # 숨김 툴팁에서 전화·고객번호·이전방문 추출
    assert r1["고객명"] == "배상웅" and r1["전화번호"] == "010-1234-7305"
    assert r1["고객번호"] == "0005120" and r1["이전방문"] == "2026-05-29"
    # 상세메뉴는 title 속성 우선, 메모는 '상세보기' 제거
    assert r1["상세메뉴"] == "남자컷(부원장)" and r1["메모"] == "손상 신경 씀"
    assert r1["결제액"] == "28000"                           # 콤마 제거
    # 연속행(빈 날짜·고객명) → 직전 고객 승계
    assert r2["고객명"] == "배상웅" and r2["상세메뉴"] == "다운펌(부원장)"
    assert r2["전화번호"] == "010-1234-7305"
    # 2페이지(gotoP) 행
    assert r3["고객명"] == "조희진" and r3["고객번호"] == "0002767"


def test_harvest_no_table(page):
    r = _harvest(page, "<html><body><p>빈 화면</p></body></html>")
    assert r["error"] == "no-table" and r["rows"] == []


# 실기기 342/727 회귀: 마지막 페이지는 stall 이 아니라 '완료'. 페이저에 현재보다 큰 gotoP 가
# 없으면(=끝) 정상 종료해야 한다. '총 N개'(건수 727)가 행수(1)보다 커도 부분수집 아님.
# + 핸드SOS 의 '다음'(checkSubmit plusDay=다음날) 버튼은 페이지네이션이 아니므로 절대 안 눌러야 함.
LAST_PAGE = """<!doctype html><html><body>
<div>총 727개</div>
<table id="list_tbl">
 <tr><th>날짜</th><th>고객명</th><th>상세메뉴</th><th>담당</th><th>결제액</th><th>메모</th></tr>
 <tr><td>26-06-26 10:00</td><td>김</td><td title="컷">컷</td><td>하예원</td><td>10,000</td><td></td></tr>
</table>
<table><tr>
 <th onclick="javascript:gotoP(0)" class="prevPage">이전</th>
 <td onclick="javascript:gotoP(1)" class="current">1</td>
</tr></table>
<a href="javascript:;" onclick="checkSubmit('plusDay');window.__plusDayClicked=true;">다음</a>
</body></html>"""


def test_last_page_is_complete_not_stall(page):
    # 현재가 마지막 페이지(gotoP>현재 없음) → 완료(error null). '건수 727'과 행수 무관.
    r = _harvest(page, LAST_PAGE)
    assert r["error"] is None and r.get("complete") is True   # 342/727 오판 방지
    assert len(r["rows"]) == 1
    assert page.evaluate("()=>!window.__plusDayClicked")      # 날짜 '다음' 버튼은 안 눌림(안전)


def test_stall_when_next_exists_but_cannot_advance(page):
    # 페이저엔 gotoP(2)가 있는데(=다음 있음) 실제 gotoP 는 아무 것도 안 함 → pagination-stalled + 덤프
    html = """<html><body><div>총 9개</div>
      <table id="list_tbl"><tr><th>날짜</th><th>고객명</th><th>상세메뉴</th><th>담당</th><th>결제액</th><th>메모</th></tr>
      <tr><td>26-06-26 10:00</td><td>김</td><td title="컷">컷</td><td>하예원</td><td>10,000</td><td></td></tr></table>
      <table><tr><td onclick="gotoP(1)" class="current">1</td><td onclick="gotoP(2)">2</td></tr></table>
      <script>window.gotoP=function(n){/* 아무 것도 안 함(멈춤 재현) */};</script></body></html>"""
    r = page.set_content(html) or page.add_script_tag(content=HARVEST_JS.read_text(encoding="utf-8"))
    r = page.evaluate("__handsosHarvest({waitTries:2})")      # 빠른 stall
    assert r["error"] == "pagination-stalled"
    assert r.get("pager") and "gotoP(2)" in r["pager"]        # 진단용 컨트롤 목록
