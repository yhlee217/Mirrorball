"""핸드SOS 매출상세목록 임포터 테스트."""

import csv
import io

import import_handsos as ih


def _w(path, rows, enc="cp949"):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    path.write_bytes(buf.getvalue().encode(enc))


# 화면 형식 모사: 날짜 / 고객명 / 핸드폰 / 구분 / 메뉴 / 상세메뉴 / 담당 / 판매가 / 결제액 / 방문
HEADER = ["날짜", "고객명", "핸드폰", "구분", "메뉴", "상세메뉴", "담당", "판매가", "결제액", "방문"]
ROWS = [
    ["26-06-26 19:41", "배상웅", "010-1234-7305", "시술", "컷", "남자컷(부원장)", "하예원", "28000", "28000", "재방"],
    ["26-05-30 13:00", "배상웅", "010-1234-7305", "시술", "펌", "다운펌(부원장)", "하예원", "130000", "91000", "재방"],
    ["26-06-26 11:58", "조희진", "010-0000-0218", "시술", "클리닉", "모발클리닉", "하예원", "80000", "80000", "재방"],
    ["26-06-26 10:00", "김주환", "010-0000-1111", "시술", "컷", "여자컷(원장)", "주환원", "30000", "30000", "재방"],
]


def test_parse_and_clean(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [HEADER] + ROWS)
    rows = ih.parse_rows(str(p))
    assert len(rows) == 4
    r0 = rows[0]
    assert r0["date"] == "2026-06-26"          # 2자리 연도 → 2026
    assert r0["service"] == "남자컷"             # (부원장) 제거
    assert r0["price"] == 28000


def test_staff_filter(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [HEADER] + ROWS)
    rows = ih.parse_rows(str(p), staff="하예원")
    assert all(r["name"] != "김주환" for r in rows)   # 주환원 제외
    assert len(rows) == 3


def test_build_customers_groups_and_counts(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [HEADER] + ROWS)
    custs = ih.build_customers(ih.parse_rows(str(p), staff="하예원"))
    by = {c["name"]: c for c in custs}
    assert by["배상웅"]["loyalty_visits"] == 2       # 6/26 + 5/30 = 2 방문
    assert len(by["배상웅"]["history"]) == 2
    assert by["배상웅"]["history"][0]["date"] == "2026-06-26"   # 최근이 위
    assert by["조희진"]["loyalty_visits"] == 1


def test_write_preserves_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "h.csv"
    _w(p, [HEADER] + ROWS)
    rows = ih.parse_rows(str(p), staff="하예원")
    custs = ih.build_customers(rows)
    # 기존 카르테(메모) 미리 존재
    cdir = tmp_path / "clients" / "hayewoni" / "customers"
    cdir.mkdir(parents=True)
    cid = ih._cid("배상웅", "010-1234-7305")
    (cdir / f"{cid}.yaml").write_text("id: x\nname: 배상웅\nmemo: 기존\n", encoding="utf-8")
    ih.write_out("hayewoni", rows, custs)
    assert "기존" in (cdir / f"{cid}.yaml").read_text(encoding="utf-8")   # 보존
    assert (tmp_path / "clients" / "hayewoni" / "records.yaml").exists()


def test_missing_required_raises(tmp_path):
    p = tmp_path / "bad.csv"
    _w(p, [["가격", "비고"], ["1", "x"]])
    try:
        ih.parse_rows(str(p))
        assert False
    except ValueError:
        pass
