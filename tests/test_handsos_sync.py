"""핸드SOS 동기화 — 브라우저 없는 순수 헬퍼 테스트(로그인/수확은 실기기에서)."""

import csv
import importlib.util
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("handsos_sync", ROOT / "scripts" / "handsos_sync.py")
hs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hs)


def test_load_stores_filters_disabled(tmp_path):
    p = tmp_path / "stores.yaml"
    p.write_text(
        "stores:\n"
        "  - slug: a\n    enabled: true\n"
        "  - slug: b\n    enabled: false\n",
        encoding="utf-8")
    rows = hs.load_stores(str(p))
    assert [s["slug"] for s in rows] == ["a"]   # disabled 제외


def test_load_stores_requires_slug(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("stores:\n  - company_code: x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        hs.load_stores(str(p))


def test_write_csv_matches_import_columns(tmp_path):
    rows = [{"날짜": "2026-06-26", "고객명": "배상웅", "전화번호": "010-1-2",
             "고객번호": "5120", "이전방문": "2026-05-29", "상세메뉴": "남자컷(부원장)",
             "담당": "하예원", "결제액": "28000", "메모": "손상 신경 씀", "여분": "무시"}]
    out = tmp_path / "h.csv"
    n = hs.write_csv(rows, out)
    assert n == 1
    with out.open(encoding="utf-8-sig") as f:
        r = list(csv.DictReader(f))
    assert list(r[0].keys()) == hs.COLS            # import_handsos 가 읽는 헤더와 일치
    assert "여분" not in r[0] and r[0]["고객번호"] == "5120"


def test_write_csv_roundtrips_into_importer(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT))
    import import_handsos as ih
    rows = [{"날짜": "2026-06-26", "고객명": "조희진", "전화번호": "010-9",
             "고객번호": "2767", "이전방문": "", "상세메뉴": "모발클리닉",
             "담당": "하예원", "결제액": "80000", "메모": "임신 중"}]
    out = tmp_path / "h.csv"
    hs.write_csv(rows, out)
    parsed = ih.parse_rows(str(out))
    assert parsed and parsed[0]["name"] == "조희진" and parsed[0]["custno"] == "2767"


def test_date_range_value():
    assert hs.date_range_value(0) == ("", "")                    # 전체
    s, e = hs.date_range_value(30, today=date(2026, 6, 30))
    assert s == "2026-05-31" and e == "2026-06-30"


def test_notify_falls_back_to_stderr_without_url(capsys):
    hs.notify({}, "테스트 알림")
    assert "테스트 알림" in capsys.readouterr().err


def test_apply_overrides_merges(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "demo.selectors.yaml").write_text(
        "report:\n  date_from_sel: '#NEW'\nlogin:\n  fields:\n    company_code: '#cc'\n", encoding="utf-8")
    store = {"slug": "demo", "login": {"fields": {"username": "#u"}},
             "report": {"url": "x", "date_from_sel": "#OLD"}}
    hs.apply_overrides(store)
    assert store["report"]["date_from_sel"] == "#NEW" and store["report"]["url"] == "x"   # 부분 갱신
    assert store["login"]["fields"]["company_code"] == "#cc" and store["login"]["fields"]["username"] == "#u"


def test_status_and_healthcheck(tmp_path, monkeypatch):
    import json as _j
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    hs.write_status("demo", {"ok": True, "rows": 5, "txns": 5})
    sp = tmp_path / "clients" / "demo" / "_status.json"
    st = _j.loads(sp.read_text(encoding="utf-8"))
    assert st["ok"] and st["last_success"]
    assert hs.healthcheck({}, max_hours=48) == 0           # 방금 성공 → 정상
    st["last_success"] = "2020-01-01T00:00:00"
    sp.write_text(_j.dumps(st), encoding="utf-8")
    assert hs.healthcheck({}, max_hours=48) == 1           # 오래 미성공 → 점검


def test_write_status_keeps_last_success_on_failure(tmp_path, monkeypatch):
    import json as _j
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    hs.write_status("demo", {"ok": True, "rows": 3})
    prev = _j.loads((tmp_path / "clients" / "demo" / "_status.json").read_text(encoding="utf-8"))["last_success"]
    hs.write_status("demo", {"ok": False, "error": "no-table"})  # 실패해도 직전 성공시각 유지
    st = _j.loads((tmp_path / "clients" / "demo" / "_status.json").read_text(encoding="utf-8"))
    assert st["ok"] is False and st["last_success"] == prev


# ── ③ 부분성공 정직화(에러 기반 — '총 N개'는 건수라 목록 행수와 대조 안 함) ──
def test_partial_of_is_error_based():
    # 마지막 페이지까지 정상 도달(error 없음)이면 행수<건수여도 완전 수집(342행 vs 727건 정상)
    assert hs.partial_of({"rows": [1] * 342, "total": 727, "complete": True}) is None
    assert hs.partial_of({"rows": [1] * 342, "total": 727, "error": None}) is None
    assert hs.partial_of({"rows": [1] * 5, "error": "pagination-stalled"}) == "pagination-stalled"
    assert hs.partial_of({"rows": [1] * 5, "error": "no-next-control"}) == "no-next-control"


# ── ④ 자가치유 자동 루프 — 검증 통과 시에만 적용 ──
class _FakeHeal:
    @staticmethod
    def pick_relevant_html(d):
        return "<html>companyID list_tbl</html>"

    @staticmethod
    def build_prompt(slug, html, err):
        return "prompt"

    @staticmethod
    def run_claude(prompt, timeout=180):
        return "```yaml\nreport:\n  search_sel: 'a.newSearch'\n```"

    @staticmethod
    def parse_selectors(out):
        return {"report": {"search_sel": "a.newSearch"}}


def _fail_res(tmp_path):
    d = tmp_path / "fail_x"
    d.mkdir(parents=True, exist_ok=True)
    (d / "page0.html").write_text("x", encoding="utf-8")
    return {"rows": [], "error": "no-table", "fail_dir": str(d)}


def test_auto_heal_applies_after_verified_reharvest(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "_load_heal", lambda: _FakeHeal)
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    used = []
    monkeypatch.setattr(hs, "harvest_store", lambda store, headed=False, debug=False:
                        (used.append(store.get("report", {}).get("search_sel"))
                         or {"rows": [{"날짜": "2026-06-26"}], "total": 1, "error": None}))
    store = {"slug": "demo"}
    out = hs.auto_heal(store, _fail_res(tmp_path), headed=False, cfg={})
    assert out and len(out["rows"]) == 1
    assert used == ["a.newSearch"]                       # 제안 셀렉터로 검증 재수확
    assert (tmp_path / "secrets" / "demo.selectors.yaml").exists()   # 통과 → 영구 적용
    assert store["report"]["search_sel"] == "a.newSearch"            # 이후 실행에도 반영


def test_auto_heal_discards_unverified_proposal(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "_load_heal", lambda: _FakeHeal)
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    monkeypatch.setattr(hs, "harvest_store",
                        lambda store, headed=False, debug=False: {"rows": [], "error": "no-table"})
    out = hs.auto_heal({"slug": "demo"}, _fail_res(tmp_path), headed=False, cfg={})
    assert out is None                                    # 검증 실패(0행) → 적용 안 함
    assert not (tmp_path / "secrets" / "demo.selectors.yaml").exists()


def test_selectors_yaml_is_single_source():
    # sync 와 heal 이 같은 canonical 파일을 읽는지(단일 진실)
    sel = hs.load_selectors()
    assert sel["login"]["fields"]["company_code"] == "#companyID"
    assert sel["report"]["result_table"] == "#list_tbl"
    spec2 = importlib.util.spec_from_file_location("handsos_heal", ROOT / "scripts" / "handsos_heal.py")
    heal = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(heal)
    assert heal.CURRENT["report"]["search_sel"] == sel["report"]["search_sel"]
    assert "list_tbl" in heal.ANCHORS


# ── 담당별 분리(멀티 디자이너) ──
def test_import_build_one_splits_by_designer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    import csv as _csv
    raw = tmp_path / "h.csv"
    with raw.open("w", encoding="utf-8-sig", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["날짜", "고객명", "전화번호", "고객번호", "이전방문", "상세메뉴", "담당", "결제액", "메모"])
        w.writerow(["2026-06-26", "김", "010-1", "1", "", "컷", "하예원", "20000", ""])
        w.writerow(["2026-06-26", "박", "010-2", "2", "", "컷", "김민지", "20000", ""])
    r = hs._import_build_one(raw, "hayewoni", "하예원", "살롱톤", do_build=False)
    assert r["txns"] == 1 and r["staff"] == "하예원"
    import yaml as _y
    custs = list((tmp_path / "clients" / "hayewoni" / "customers").glob("*.yaml"))
    names = {_y.safe_load(p.read_text(encoding="utf-8"))["name"] for p in custs}
    assert names == {"김"}                               # 다른 디자이너(김민지) 고객 제외


def test_slug_for_strips_role_and_sanitizes():
    assert hs._slug_for("하예원 부원장") == "하예원"
    assert hs._slug_for("김민지") == "김민지"
    assert hs._slug_for("Jenny(원장)") == "Jenny"
    assert hs._slug_for("") is None


def test_write_out_base_dir_is_location_independent(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT))
    import import_handsos as ih
    # CWD 와 무관하게 base_dir 아래에 저장
    ih.write_out("hayewoni", [{"date": "2026-06-26", "name": "김", "custno": "1",
                               "service": "컷", "price": 20000}],
                 base_dir=tmp_path / "clients")
    assert (tmp_path / "clients" / "hayewoni" / "records.yaml").exists()
    assert (tmp_path / "clients" / "hayewoni" / "customers").exists()


def test_prune_raw_keeps_latest_csv_and_recent_fails(tmp_path):
    d = tmp_path / "_raw"
    d.mkdir()
    (d / "handsos_latest.csv").write_text("keep", encoding="utf-8")   # 최신본(보존)
    for i in range(6):
        (d / f"handsos_2026010{i}-000000.csv").write_text("old", encoding="utf-8")  # 옛 스냅샷
    for i in range(4):
        (d / f"fail_2026010{i}-000000").mkdir()
    removed = hs.prune_raw(d, keep=3)
    assert {p.name for p in d.glob("*.csv")} == {"handsos_latest.csv"}  # 최신본만 남음
    assert len([x for x in d.glob("fail_*") if x.is_dir()]) == 3        # fail 최근 3개
    assert removed == 6 + 1                                             # 옛 csv 6 + fail 1
