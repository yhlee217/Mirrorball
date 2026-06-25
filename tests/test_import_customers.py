"""고객 마스터 임포터 테스트 — import_customers."""

import csv
import io

import import_customers as ic


def _w(path, rows, enc="utf-8"):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    path.write_bytes(buf.getvalue().encode(enc))


HEADER = ["고객명", "연락처", "생년월일", "방문횟수", "최근방문", "최근시술", "메모", "선호"]


def test_parse_maps_columns(tmp_path):
    p = tmp_path / "c.csv"
    _w(p, [HEADER,
           ["김문규", "010-1111-2222", "1990-03-12", "67", "2026-06-16", "다운펌", "손상 민감", "디테일/자연스러움"]])
    rows = ic.parse_customers(str(p))
    c = rows[0]
    assert c["name"] == "김문규" and c["contact"] == "010-1111-2222"
    assert c["birthday"] == "03-12" and c["loyalty_visits"] == 67
    assert c["memo"] == "손상 민감" and c["prefer"] == ["디테일", "자연스러움"]
    assert c["history"][0] == {"date": "2026-06-16", "service": "다운펌"}


def test_cp949_and_alias_headers(tmp_path):
    p = tmp_path / "c2.csv"
    _w(p, [["성함", "휴대폰", "누적방문"], ["조희진", "010-3", "80"]], enc="cp949")
    rows = ic.parse_customers(str(p))
    assert rows[0]["name"] == "조희진" and rows[0]["loyalty_visits"] == 80


def test_missing_name_column_raises(tmp_path):
    p = tmp_path / "bad.csv"
    _w(p, [["메모", "기타"], ["x", "y"]])
    try:
        ic.parse_customers(str(p))
        assert False
    except ValueError:
        pass


def test_dedupe_by_phone(tmp_path):
    custs = [{"id": "a", "name": "김", "contact": "010-1"},
             {"id": "b", "name": "김중복", "contact": "010-1"}]
    assert len(ic.dedupe(custs)) == 1


def test_write_preserves_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cdir = tmp_path / "clients" / "demo" / "customers"
    cdir.mkdir(parents=True)
    (cdir / "김문규.yaml").write_text("id: 김문규\nname: 김문규\nmemo: 기존메모\n", encoding="utf-8")
    n = ic.write_customers("demo", [{"id": "김문규", "name": "김문규"}, {"id": "이새", "name": "이새"}])
    assert n == 1                                    # 기존은 보존, 신규 1명만
    import yaml
    assert "기존메모" in (cdir / "김문규.yaml").read_text(encoding="utf-8")
