"""네이버 예약 CSV 임포터 테스트 — 컬럼 인식·정규화·취소 제외."""

import csv
import io

import import_naver as imp


def _write(path, rows, enc="utf-8"):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    path.write_bytes(buf.getvalue().encode(enc))


HEADER = ["예약번호", "예약일", "예약시간", "예약자명", "예약상품", "연락처", "예약상태"]


def test_parse_basic_and_cancel_excluded(tmp_path):
    p = tmp_path / "e.csv"
    _write(p, [
        HEADER,
        ["A1", "2026. 6. 23.", "오후 2:00", "지우", "레이어드펌", "010-1111-2222", "확정"],
        ["A2", "2026-06-23(화)", "16:30", "박손님", "발레아주", "010-3333-4444", "확정"],
        ["A3", "2026. 6. 24.", "11:00", "취소손님", "커트", "010-5", "예약취소"],
    ])
    rows = imp.parse_csv(str(p))
    assert len(rows) == 2                      # 취소 1건 제외
    r0 = rows[0]
    assert r0["date"] == "2026-06-23" and r0["time"] == "14:00"
    assert r0["name"] == "지우" and r0["service"] == "레이어드펌"
    assert r0["phone"] == "010-1111-2222" and r0["rid"] == "A1"   # 예약번호 캡처
    assert rows[1]["time"] == "16:30" and rows[1]["date"] == "2026-06-23"


def test_price_parsing_and_records_append(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "e.csv"
    _write(p, [
        ["예약번호", "예약일", "예약시간", "예약자명", "상품명", "결제금액", "상태"],
        ["R1", "2026-06-23", "14:00", "지우", "펌", "180,000원", "완료"],
        ["R2", "2026-06-23", "16:00", "박", "컷", "3만원", "완료"],
    ])
    rows = imp.parse_csv(str(p))
    assert rows[0]["price"] == 180000 and rows[1]["price"] == 30000
    # 누적 원장에 적재 + dedup
    _, total, added = imp.append_records("minji", rows)
    assert total == 2 and added == 2
    _, total2, added2 = imp.append_records("minji", rows)  # 같은 예약번호 → 추가 0
    assert total2 == 2 and added2 == 0


def test_cp949_encoding(tmp_path):
    p = tmp_path / "e_cp949.csv"
    _write(p, [HEADER, ["A1", "2026-06-23", "10:00", "김고객", "컷", "010-0", "확정"]], enc="cp949")
    rows = imp.parse_csv(str(p))
    assert rows[0]["name"] == "김고객"


def test_column_alias_detection(tmp_path):
    # 다른 헤더 이름이어도 인식 (고객명/날짜/시간/메뉴)
    p = tmp_path / "e2.csv"
    _write(p, [
        ["날짜", "시간", "고객명", "메뉴", "전화번호"],
        ["2026-06-23", "13:00", "이손님", "펌", "010-9"],
    ])
    rows = imp.parse_csv(str(p))
    assert rows and rows[0]["name"] == "이손님" and rows[0]["service"] == "펌"


def test_time_normalization():
    assert imp._clean_time("오후 2:00") == "14:00"
    assert imp._clean_time("오전 9:30") == "09:30"
    assert imp._clean_time("14시") == "14:00"


def test_missing_required_columns_raises(tmp_path):
    p = tmp_path / "bad.csv"
    _write(p, [["메모", "기타"], ["x", "y"]])
    try:
        imp.parse_csv(str(p))
        assert False, "필수 컬럼 누락 시 예외가 나야 함"
    except ValueError:
        pass


def test_write_bookings_date_filter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bookings = [
        {"date": "2026-06-23", "time": "14:00", "name": "A", "service": "s", "phone": "1"},
        {"date": "2026-06-24", "time": "10:00", "name": "B", "service": "s", "phone": "2"},
    ]
    out = imp.write_bookings("minji", bookings, date="2026-06-23")
    import yaml
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert len(data) == 1 and data[0]["name"] == "A"
