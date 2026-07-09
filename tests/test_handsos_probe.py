"""handsos_probe 순수 파서 테스트 — 브라우저 없이 메뉴 추출·생일 컨텍스트 추출 계약 고정.

진단 도구의 '무엇을 찾아 보여줄지'(고객 메뉴 후보, 생일 주변 텍스트)를 합성 HTML 로 못박는다.
실제 핸드SOS DOM 은 실행 시 확인하지만, 파서의 계약이 바뀌는 건 여기서 잡는다.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "handsos_probe", ROOT / "scripts" / "handsos_probe.py")
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


MENU_HTML = """
<ul id="gnb">
  <li><a href="/work/detail/saleList.asp">매출상세목록</a></li>
  <li><a href="/work/customer/customerList.asp">고객관리</a></li>
  <li><a href="#" onclick="goMenu('member');return false;">회원조회</a></li>
  <li><a href="#">공지사항</a></li>
  <li><a>장식용</a></li>
</ul>
"""


def test_menu_links_drops_decorative():
    links = probe.menu_links_from_html(MENU_HTML)
    texts = [l["text"] for l in links]
    assert "매출상세목록" in texts and "고객관리" in texts
    assert "회원조회" in texts                    # onclick 만 있어도 유효
    assert "공지사항" not in texts                # href='#' + onclick 없음 → 제외
    assert "장식용" not in texts                  # href/onclick 전무 → 제외


def test_customer_menu_candidates_filters_to_customer():
    cands = probe.customer_menu_candidates(probe.menu_links_from_html(MENU_HTML))
    texts = [c["text"] for c in cands]
    assert "고객관리" in texts and "회원조회" in texts
    assert "매출상세목록" not in texts            # '고객/회원/생일' 없음
    # href 로도 매칭: customerList.asp 는 'customer' 포함
    assert any("customerList" in c["href"] for c in cands)


def test_customer_candidates_dedup():
    html = ('<a href="/c.asp">고객관리</a>'
            '<a href="/c.asp">고객관리</a>')     # 동일 링크 2번
    cands = probe.customer_menu_candidates(probe.menu_links_from_html(html))
    assert len(cands) == 1


BDAY_HTML = """
<table>
  <tr><th>이름</th><th>생년월일</th><th>연락처</th></tr>
  <tr><td>배상웅</td><td>1990-03-15</td><td>010-1234-7305</td></tr>
</table>
<div class="info">생일: 03/15 · 최근방문 2026-06-26</div>
"""


def test_birthday_context_finds_both_labels():
    ctx = probe.birthday_context(BDAY_HTML)
    joined = " || ".join(ctx)
    assert "생년월일" in joined and "생일" in joined
    # 생년월일 주변에 실제 날짜값이 함께 잡혀야(인접 칼럼 확인 목적)
    assert "1990-03-15" in joined
    assert "03/15" in joined


def test_birthday_context_empty_when_absent():
    assert probe.birthday_context("<div>매출 통계만 있는 화면</div>") == []


def test_text_strips_tags_and_ws():
    assert probe._text("<div>  가  <b>나</b>\n다 </div>") == "가 나 다"
