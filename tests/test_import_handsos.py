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


# ── 실제 핸드SOS 내보내기 형식(고객명 칸에 툴팁 오염, 전화번호·고객번호·메모 별도 칸) ──
H2 = ["날짜", "고객명", "전화번호", "고객번호", "이전방문", "상세메뉴", "담당", "결제액", "메모"]


def test_clean_polluted_name_and_custno_memo(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["2026-06-26", "배상웅*전화 번호: 010-2114-7305*고객 번호: 0005120", "010-2114-7305", "0005120",
            "2026-05-29", "남자컷(부원장)", "하예원", "28000", "손상 신경 씀"]])
    rows = ih.parse_rows(str(p))
    r = rows[0]
    assert r["name"] == "배상웅"           # 툴팁 제거
    assert r["phone"] == "010-2114-7305"
    assert r["custno"] == "5120"           # 숫자만
    assert r["memo"] == "손상 신경 씀"


def test_date_carryforward_continuation(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["2026-06-26", "배상웅", "010-1", "100", "", "컷", "하예원", "28000", ""],
           ["", "배상웅", "010-1", "100", "", "염색", "하예원", "60000", ""]])  # 연속행: 날짜 빈칸
    rows = ih.parse_rows(str(p))
    assert len(rows) == 2 and rows[1]["date"] == "2026-06-26"   # 직전 날짜 이어받음


def test_custno_grouping_and_memo_notes(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["2026-01-02", "조희진", "010-9", "0002767", "", "뿌리염색", "하예원", "30000", "수다 좋아함"],
           ["2026-06-26", "조희진", "010-9", "0002767", "", "모발클리닉", "하예원", "80000", "임신 중"]])
    custs = ih.build_customers(ih.parse_rows(str(p)))
    assert len(custs) == 1                          # 고객번호로 한 명
    c = custs[0]
    assert c["id"] == "c2767" and c["loyalty_visits"] == 2 and c["custno"] == "2767"
    notes = [h.get("notes") for h in c["history"]]
    assert "임신 중" in notes and "수다 좋아함" in notes   # 메모 → 방문 노트


def test_anon_walkins_excluded_from_customers(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["2026-06-26", "손님", "", "", "", "남자컷", "하예원", "20000", ""],
           ["2026-06-20", "손님", "", "", "", "남자컷", "하예원", "20000", ""],
           ["2026-06-26", "조희진", "010-9", "0002767", "", "모발클리닉", "하예원", "80000", ""]])
    rows = ih.parse_rows(str(p))
    assert len(rows) == 3                                   # 장부엔 모두 보존(매출 통계용)
    custs = ih.build_customers(rows)
    names = {c["name"] for c in custs}
    assert "손님" not in names and "조희진" in names         # 워크인은 고객 카드 미생성
    assert len(custs) == 1


def test_stats_excludes_anon_from_customer_metrics():
    import stats
    recs = [
        {"date": "2026-06-01", "name": "손님", "service": "컷", "price": 20000},
        {"date": "2026-06-02", "name": "손님", "service": "컷", "price": 20000},
        {"date": "2026-06-03", "name": "김", "phone": "010-1", "service": "컷", "price": 30000},
        {"date": "2026-06-10", "name": "김", "phone": "010-1", "service": "펌", "price": 90000},
    ]
    s = stats.compute(recs, today=__import__("datetime").date(2026, 6, 26))
    assert s["unique_customers"] == 1 and s["returning_customers"] == 1   # 손님 제외, 김만
    assert s["anon_visits"] == 2
    assert s["total_visits"] == 4                                          # 매출/방문 총계엔 포함


def test_build_app_redacts_phone_in_notes(tmp_path):
    import build_app
    cdir = tmp_path / "clients" / "demo"
    (cdir / "customers").mkdir(parents=True)
    (cdir / "config.yaml").write_text("slug: demo\ntoday: 2026-06-23\n", encoding="utf-8")
    (cdir / "customers" / "x.yaml").write_text(
        "id: x\nname: 김\nhistory:\n  - date: 2026-06-01\n    service: 컷\n    notes: '연락 010-1234-5678 로'\n",
        encoding="utf-8")
    build_app.build_one(str(cdir), dist=str(tmp_path / "out"))
    blob = (tmp_path / "out" / "demo.json").read_text(encoding="utf-8")
    assert "010-1234-5678" not in blob and "[연락처]" in blob   # 메모 속 번호 마스킹
