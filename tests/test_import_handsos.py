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


def test_write_out_accumulates_across_runs(tmp_path, monkeypatch):
    # 400일 제한으로 기간을 나눠 받아도 records 가 누적되고 고객 이력이 합쳐져야 함
    monkeypatch.chdir(tmp_path)
    r2025 = [{"date": "2025-08-01", "name": "조희진", "custno": "2767", "service": "뿌리염색", "price": 30000}]
    r2026 = [{"date": "2026-06-26", "name": "조희진", "custno": "2767", "service": "모발클리닉", "price": 80000}]
    ih.write_out("hayewoni", r2025)
    ih.write_out("hayewoni", r2026)                 # 두 번째 실행 — 덮어쓰지 않고 누적
    import yaml as _y
    recs = _y.safe_load((tmp_path / "clients" / "hayewoni" / "records.yaml").read_text(encoding="utf-8"))
    assert len(recs) == 2                            # 2025 + 2026 둘 다
    cust = _y.safe_load((tmp_path / "clients" / "hayewoni" / "customers" / "c2767.yaml").read_text(encoding="utf-8"))
    assert cust["loyalty_visits"] == 2               # 이력이 합쳐짐
    dates = [h["date"] for h in cust["history"]]
    assert "2025-08-01" in dates and "2026-06-26" in dates


def test_write_out_preserves_manual_on_resync(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ih.write_out("demo", [{"date": "2026-01-02", "name": "김", "custno": "5", "service": "컷", "price": 20000}])
    p = tmp_path / "clients" / "demo" / "customers" / "c5.yaml"
    import yaml as _y
    d = _y.safe_load(p.read_text(encoding="utf-8")); d["memo"] = "손상 신경 씀"; d["prefer"] = ["밝은색"]
    p.write_text(_y.safe_dump(d, allow_unicode=True), encoding="utf-8")
    ih.write_out("demo", [{"date": "2026-03-03", "name": "김", "custno": "5", "service": "펌", "price": 90000}])
    d2 = _y.safe_load(p.read_text(encoding="utf-8"))
    assert d2["memo"] == "손상 신경 씀" and d2["prefer"] == ["밝은색"]   # 수동필드 보존
    assert d2["loyalty_visits"] == 2                                    # 이력은 갱신


# ── ① 아이덴티티·병합 정비 ──
def test_custno_all_zero_preserved():
    assert ih._custno("0005120") == "5120"
    assert ih._custno("0") == "0" and ih._custno("000") == "000"   # 전부-0 은 빈값化 금지
    assert ih._custno("") == "" and ih._custno(None) == ""


def test_merge_replaces_group_on_memo_or_price_edit():
    # 핸드SOS에서 메모/금액을 수정해 재수확 → 신·구 2건이 아니라 최신 1건
    old = [{"date": "2026-06-01", "name": "김", "custno": "5", "service": "컷",
            "price": 20000, "memo": "옛 메모"}]
    new = [{"date": "2026-06-01", "name": "김", "custno": "5", "service": "컷",
            "price": 25000, "memo": "고친 메모"}]
    merged = ih.merge_records(old, new)
    assert len(merged) == 1 and merged[0]["price"] == 25000 and merged[0]["memo"] == "고친 메모"


def test_merge_keeps_other_dates_and_same_day_pair():
    # 새 스크랩 범위 밖 날짜는 유지 + 같은 방문에 같은 시술 2건(금액 다름)은 붕괴 안 함
    old = [{"date": "2025-08-01", "name": "김", "custno": "5", "service": "펌", "price": 90000}]
    new = [{"date": "2026-06-01", "name": "김", "custno": "5", "service": "클리닉", "price": 40000},
           {"date": "2026-06-01", "name": "김", "custno": "5", "service": "클리닉", "price": 30000}]
    merged = ih.merge_records(old, new)
    assert len(merged) == 3
    assert sum(1 for r in merged if r["service"] == "클리닉") == 2


def test_reconcile_merges_split_cards():
    # 같은 손님: 6월 방문엔 custno 없음, 1월 방문엔 있음 → 카드 1장으로
    rows = [
        {"date": "2026-01-02", "name": "조희진", "phone": "010-9", "custno": "2767",
         "service": "뿌리염색", "price": 30000},
        {"date": "2026-06-26", "name": "조희진", "phone": "010-9",
         "service": "모발클리닉", "price": 80000},          # custno 누락 방문
    ]
    merges = []
    custs = ih.build_customers(rows, merges=merges)
    assert len(custs) == 1 and custs[0]["custno"] == "2767"
    assert custs[0]["loyalty_visits"] == 2                   # 방문·매출 안 갈라짐
    assert merges and merges[0]["custno"] == "2767"


def test_reconcile_skips_ambiguous_same_name():
    # 동명이인(전화 다름) → 병합 안 함
    rows = [
        {"date": "2026-01-02", "name": "김민지", "phone": "010-1", "custno": "1", "service": "컷"},
        {"date": "2026-02-02", "name": "김민지", "phone": "010-2", "service": "펌"},   # 다른 사람
    ]
    custs = ih.build_customers(rows)
    assert len(custs) == 2


def test_write_out_reconcile_moves_manual_and_removes_orphan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # 1차: custno 없는 방문만 → np 카드 생성, 수동 메모 기입
    ih.write_out("demo", [{"date": "2026-06-01", "name": "조희진", "phone": "010-9",
                           "service": "컷", "price": 20000}])
    import yaml as _y
    np_p = tmp_path / "clients" / "demo" / "customers" / f"{ih._cid('조희진', '010-9')}.yaml"
    d = _y.safe_load(np_p.read_text(encoding="utf-8")); d["memo"] = "수다 좋아함"
    np_p.write_text(_y.safe_dump(d, allow_unicode=True), encoding="utf-8")
    # 2차: custno 있는 방문 도착 → 화해 병합
    ih.write_out("demo", [{"date": "2026-06-20", "name": "조희진", "phone": "010-9",
                           "custno": "2767", "service": "펌", "price": 90000}])
    assert not np_p.exists()                                   # 고아 카드 정리
    c = _y.safe_load((tmp_path / "clients" / "demo" / "customers" / "c2767.yaml")
                     .read_text(encoding="utf-8"))
    assert c["loyalty_visits"] == 2 and c["memo"] == "수다 좋아함"   # 이력 합침 + 수동 승계


def test_merge_records_idempotent_on_rerun():
    # 같은 데이터를 다시 수집해도 원장이 안 늘어남(중복 누적 방지)
    rows = [{"date": "2026-06-26", "name": "김", "custno": "1", "service": "컷", "price": 20000},
            {"date": "2026-06-25", "name": "이", "custno": "2", "service": "펌", "price": 90000}]
    once = ih.merge_records([], rows)
    twice = ih.merge_records(once, rows)          # 재실행(동일 스크랩)
    thrice = ih.merge_records(twice, rows)
    assert len(once) == len(twice) == len(thrice) == 2


def test_anon_identical_rows_survive_import():
    # 같은 날 같은 시술·금액의 익명 2건 — 붕괴하면 매출 과소집계
    rows = [{"date": "2026-06-01", "name": "손님", "service": "컷", "price": 20000},
            {"date": "2026-06-01", "name": "손님", "service": "컷", "price": 20000}]
    merged = ih.merge_records([], rows)
    assert len(merged) == 2


# ── ② 버려지던 필드 살리기 ──
def test_time_staff_prev_captured(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["26-06-26 19:41", "배상웅", "010-1", "100", "2026-05-29", "남자컷", "하예원", "28000", ""]])
    r = ih.parse_rows(str(p))[0]
    assert r["time"] == "19:41"                 # 피크시간 통계 부활
    assert r["staff"] == "하예원"                # 담당 보존
    assert r["prev_visit"] == "2026-05-29"      # 이전방문 크로스체크용


def test_stats_busiest_hour_alive_with_time():
    import stats
    recs = [{"date": "2026-06-0%d" % d, "time": "19:00", "name": "김", "phone": "1",
             "service": "컷", "price": 10000} for d in range(1, 6)]
    s = stats.compute(recs, today=__import__("datetime").date(2026, 6, 26))
    assert s.get("busiest_hour") is not None    # time 이 채워지면 피크시간이 산다


def test_birthday_column_flows_to_customer(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2[:-1] + ["생일", "메모"],
           ["2026-06-26", "조희진", "010-9", "2767", "", "컷", "하예원", "30000", "03-15", ""]])
    custs = ih.build_customers(ih.parse_rows(str(p)))
    assert custs[0]["birthday"] == "03-15"      # 생일 케어 자동 점화


def test_staff_breakdown_counts_designers():
    rows = [{"date": "2026-06-01", "name": "김", "staff": "하예원", "service": "컷"},
            {"date": "2026-06-02", "name": "이", "staff": "하예원", "service": "펌"},
            {"date": "2026-06-03", "name": "박", "staff": "김민지", "service": "컷"},
            {"date": "2026-06-04", "name": "최", "service": "컷"}]
    bd = dict(ih.staff_breakdown(rows))
    assert bd["하예원"] == 2 and bd["김민지"] == 1 and bd["(담당 미지정)"] == 1


def test_continuation_row_inherits_staff_under_filter(tmp_path):
    # 연속행(담당 빈칸) — 필터 시 직전 담당 승계로 2번째 시술이 안 빠져야 함
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["26-06-26 19:41", "배상웅", "010-1", "100", "", "컷", "하예원", "28000", ""],
           ["", "배상웅", "010-1", "100", "", "펌", "", "60000", ""]])  # 담당 빈칸(연속행)
    rows = ih.parse_rows(str(p), staff="하예원")
    assert len(rows) == 2                                # 승계로 둘 다 유지
    assert rows[1]["service"] == "펌" and rows[1]["staff"] == "하예원"


def test_no_staff_row_not_leaked_to_filtered_designer(tmp_path):
    # 담당 비어있고 승계할 직전 담당도 없는 행(무담당) → 특정 디자이너 필터엔 안 들어가야(교차오염 방지)
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["2026-06-26", "무담당손님", "010-9", "9", "", "상품", "", "10000", ""],   # 담당 빈칸(첫 행)
           ["2026-06-26", "김", "010-1", "1", "", "컷", "하예원", "20000", ""]])
    only = ih.parse_rows(str(p), staff="하예원")
    assert [r["name"] for r in only] == ["김"]           # 무담당 행 제외
    allrows = ih.parse_rows(str(p))                       # 필터 없으면 둘 다 보존
    assert len(allrows) == 2


def test_staff_filter_excludes_other_designer(tmp_path):
    p = tmp_path / "h.csv"
    _w(p, [H2,
           ["2026-06-26", "김", "010-1", "1", "", "컷", "하예원", "20000", ""],
           ["2026-06-26", "박", "010-2", "2", "", "컷", "김민지", "20000", ""]])
    only = ih.parse_rows(str(p), staff="하예원")
    assert [r["name"] for r in only] == ["김"]           # 다른 디자이너 고객 제외


def test_prev_visit_mismatch_only_in_range_holes():
    rows = [
        {"date": "2026-01-02", "name": "배상웅", "custno": "100", "service": "펌"},   # 최저
        {"date": "2026-06-26", "name": "배상웅", "custno": "100", "service": "컷",
         "prev_visit": "2026-01-02"},                      # 일치 — 정상
        {"date": "2026-06-26", "name": "조희진", "custno": "200", "service": "컷",
         "prev_visit": "2025-12-01"},                      # 범위 이전 과거 이력 → 무시(정상)
        {"date": "2026-01-05", "name": "김주환", "custno": "300", "service": "컷"},   # 최저
        {"date": "2026-06-26", "name": "김주환", "custno": "300", "service": "펌",
         "prev_visit": "2026-03-15"},                      # 범위(1/5~6/26) 안인데 없음 = 진짜 구멍
    ]
    mm = ih.prev_visit_mismatches(rows)
    assert len(mm) == 1 and mm[0]["name"] == "김주환"      # 범위 내 구멍만, 과거이력·일치는 제외


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
