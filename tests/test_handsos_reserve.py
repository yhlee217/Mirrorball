"""handsos_reserve — 예약 목록 파싱 → bookings 계약 테스트.

실제 reserveList 행 구조(진단 2026-07)로 합성 HTML을 만들어 검증:
  · 담당(디자이너) 필터 — 상세셀에 '하예원' 있는 행만
  · 상태 예약중만(취소·노쇼·완료 제외)
  · 오늘 이후만(다가오는 예약)
  · 예약시각·이름·전화·시술 정확 추출, 날짜·시간순 정렬
"""

import yaml

import handsos_reserve as hr


def _row(when, status, name, phone, detail):
    """실제 예약 행 셀 배치 재현: [.., 예약시각, .., .., 상태, 매출입력, 이름, 전화, 담당+시술, .., 등록시각, ..]."""
    return ("<tr><td></td>"
            f"<td>&nbsp;{when}</td><td></td><td></td>"
            f"<td>&nbsp; {status}</td><td>미입력</td>"
            f"<td>{name}</td><td>{phone}</td>"
            f'<td>{detail} <a href="/work/sale/sale.asp?strHowCateg=RESERVE&nInsertGroup=1&pkCustomer=1">상세</a></td>'
            "<td></td><td></td><td>&nbsp;&nbsp; 26-07-09 목 20:27</td>"
            "<td>현장결제</td><td>0</td><td>0</td><td>0</td></tr>")


HAY = "하예원. --> 상세보기 네이버 예약건 예약시술메뉴 : {svc} : 28,000원"
JU = "주환원. --> 상세보기 예약시술메뉴 : 남자컷(원장) : 38,000원"


def _html(*rows):
    return "<table id='list_tbl'><tbody>" + "".join(rows) + "</tbody></table>"


def test_parse_when():
    assert hr.parse_when("26-07-10 금 19:30") == ("2026-07-10", "19:30")
    assert hr.parse_when("26-7-5 일 9:05") == ("2026-07-05", "09:05")
    assert hr.parse_when("없음") is None


def test_parse_detail():
    assert hr.parse_detail("하예원. --> 상세보기 예약시술메뉴 : 남자컷(부원장) : 28,000원") == ("하예원", "남자컷(부원장)")
    assert hr.parse_detail("주환원. 예약시술메뉴 : 남자컷(원장)+다운펌 : 68,000원") == ("주환원", "남자컷(원장)+다운펌")


def test_harvest_hayewoni_upcoming():
    html = _html(
        _row("26-07-10 금 19:30", "예약중", "강유신", "010-6205-0677", HAY.format(svc="남자컷(부원장)")),  # keep
        _row("26-07-10 금 18:30", "예약중", "김정민", "010-4551-2020", JU),                              # skip: 담당
        _row("26-07-11 토 14:00", "취소",   "홍길동", "010-1111-2222", HAY.format(svc="펌")),             # skip: 상태
        _row("26-07-05 일 11:00", "예약중", "이순신", "010-3333-4444", HAY.format(svc="컷")),             # skip: 과거
        _row("26-07-12 월 17:00", "예약중", "김유신", "010-5555-6666", HAY.format(svc="다운펌")),          # keep
    )
    bks = hr.harvest_bookings(html, "하예원", "2026-07-10")
    assert [b["name"] for b in bks] == ["강유신", "김유신"]           # 담당·예약중·오늘이후, 날짜·시간순
    assert bks[0] == {"name": "강유신", "phone": "01062050677",
                      "service": "남자컷(부원장)", "time": "19:30", "date": "2026-07-10"}
    assert bks[1]["date"] == "2026-07-12" and bks[1]["service"] == "다운펌"


def test_none_staff_keeps_all_upcoming():
    html = _html(
        _row("26-07-10 금 19:30", "예약중", "강유신", "010-6205-0677", HAY.format(svc="컷")),
        _row("26-07-10 금 18:30", "예약중", "김정민", "010-4551-2020", JU),
    )
    assert len(hr.harvest_bookings(html, None, "2026-07-10")) == 2      # 담당 미지정 → 전부


def test_write_bookings(tmp_path):
    p = hr.write_bookings(tmp_path, [{"name": "A", "phone": "01012345678",
                                      "service": "컷", "time": "10:00", "date": "2026-07-11"}])
    data = yaml.safe_load(open(p, encoding="utf-8"))
    assert data[0]["name"] == "A" and data[0]["date"] == "2026-07-11"
