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


# ── ③ 부분성공 정직화 ──
def test_partial_of_reconciles_total():
    assert hs.partial_of({"rows": [1] * 80, "total": 100}) == "수집 80/100행"   # 조용한 미달 감지
    assert hs.partial_of({"rows": [1] * 100, "total": 100}) is None            # 완전 수집
    assert hs.partial_of({"rows": [1] * 5, "total": 0}) is None                # 총계 미파싱 → 판정 보류
    assert hs.partial_of({"rows": [1] * 5, "total": 100,
                          "error": "pagination-stalled"}) == "pagination-stalled"
