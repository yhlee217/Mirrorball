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
<span class="current" id="pg">1</span>
<script>
  window.gotoP = function(n){
    document.getElementById('tb').innerHTML =
      '<tr><td>26-06-25 11:00</td>' +
      '<td>조희진<span id="strCustomerInfo2" style="display:none">고객명 : 조희진\\n전화 번호 : 010-0000-0218\\n고객 번호 : 0002767</span></td>' +
      '<td title="모발클리닉">모발클리닉</td><td>하예원</td><td>80,000</td><td></td></tr>';
    document.getElementById('pg').textContent = String(n);
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


# 블록 페이징: 전역 gotoP 함수 없음 + 페이지번호 링크도 없음 → '›' 다음 화살표로만 넘어감.
# (실기기 342/727 stall 의 유력 원인 — 블록 경계에서 번호링크가 사라지고 화살표가 필요)
FIXTURE_BLOCK = """<!doctype html><html><body>
<div>총 2개</div>
<table id="list_tbl">
 <tr><th>날짜</th><th>고객명</th><th>상세메뉴</th><th>담당</th><th>결제액</th><th>메모</th></tr>
 <tbody id="tb">
  <tr><td>26-06-26 14:20</td><td>조희진</td><td title="뿌리염색">뿌리염색</td><td>하예원</td><td>30,000</td><td></td></tr>
 </tbody>
</table>
<div id="pager"><span class="current">1</span> <a href="#" onclick="adv();return false;">›</a></div>
<script>
 var pageNo=1;
 function adv(){ pageNo++;
   if(pageNo===2){ document.getElementById('tb').innerHTML =
     '<tr><td>26-06-20 11:00</td><td>배상웅</td><td title="남자컷">남자컷</td><td>하예원</td><td>28,000</td><td></td></tr>'; }
   var c=document.querySelector('#pager .current'); if(c) c.textContent=String(pageNo); }
</script>
</body></html>"""


def test_harvest_block_pagination_via_next_arrow(page):
    r = _harvest(page, FIXTURE_BLOCK)
    assert r["error"] is None                              # '›' 화살표로 끝까지
    names = [x["고객명"] for x in r["rows"]]
    assert names == ["조희진", "배상웅"] and len(r["rows"]) == 2


def test_stall_returns_pager_dump(page):
    # 다음 컨트롤이 아예 없는데 총건수는 더 많다고 표기 → no-next-control + 페이저 DOM 반환
    html = """<html><body><div>총 9개</div>
      <table id="list_tbl"><tr><th>날짜</th><th>고객명</th><th>상세메뉴</th><th>담당</th><th>결제액</th><th>메모</th></tr>
      <tr><td>26-06-26 10:00</td><td>김</td><td title="컷">컷</td><td>하예원</td><td>10,000</td><td></td></tr></table>
      <div id="pager"><span class="current">1</span><span onclick="gotoP(1)">1</span></div></body></html>"""
    r = _harvest(page, html)
    assert r["error"] == "no-next-control"                 # 3페이지째 넘길 데 없음
    assert "pager" in r and r["pager"]                     # 진단용 DOM 확보
