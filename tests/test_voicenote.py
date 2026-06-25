"""음성 메모 파이프라인 — 결정적 부분(파싱·매칭·반영) 테스트."""

import yaml

import voicenote as vn


def test_parse_summary_fenced_json():
    txt = '여기요\n```json\n{"customer_name":"김문규","summary":"다운펌 상담","tags":["손상 민감"],"service":"다운펌","next_action":"","care_cycle_days":null}\n```'
    d = vn.parse_summary(txt)
    assert d["customer_name"] == "김문규" and d["tags"] == ["손상 민감"]


def test_parse_summary_bare_object_in_text():
    d = vn.parse_summary('설명... {"customer_name":"조희진","summary":"s","tags":[]} 끝')
    assert d["customer_name"] == "조희진"


def test_match_customer_exact_and_contains():
    custs = [{"id": "a", "name": "김문규"}, {"id": "b", "name": "조희진"}]
    assert vn.match_customer("김문규님", custs)["id"] == "a"
    assert vn.match_customer("조희진", custs)["id"] == "b"
    assert vn.match_customer("없는사람", custs) is None


def _setup(tmp_path):
    cdir = tmp_path / "clients" / "demo" / "customers"
    cdir.mkdir(parents=True)
    (cdir / "k.yaml").write_text("id: k\nname: 김문규\nprefer: [디테일]\n", encoding="utf-8")
    return str(tmp_path / "clients" / "demo")


def test_apply_summary_writes_memo_and_tags(tmp_path):
    cd = _setup(tmp_path)
    res = vn.apply_summary(cd, {
        "customer_name": "김문규님", "summary": "다운펌, 손상 신경 많이 쓰심",
        "tags": ["손상 민감", "디테일"], "service": "다운펌",
        "next_action": "약한 약제", "care_cycle_days": 60,
    }, today="2026-06-26")
    assert res["matched"] and res["id"] == "k"
    data = yaml.safe_load(open(res["path"], encoding="utf-8"))
    assert "2026-06-26" in data["memo"] and "다운펌" in data["memo"]
    assert "다음: 약한 약제" in data["memo"]
    assert "손상 민감" in data["prefer"] and data["prefer"].count("디테일") == 1  # 중복 병합 안 함
    assert data["care_cycle_days"] == 60


def test_apply_summary_appends_to_existing_memo(tmp_path):
    cd = _setup(tmp_path)
    vn.apply_summary(cd, {"customer_name": "김문규", "summary": "첫 메모", "tags": []}, today="2026-06-01")
    res = vn.apply_summary(cd, {"customer_name": "김문규", "summary": "둘째 메모", "tags": []}, today="2026-06-26")
    data = yaml.safe_load(open(res["path"], encoding="utf-8"))
    assert "첫 메모" in data["memo"] and "둘째 메모" in data["memo"]  # 누적


def test_apply_summary_no_match(tmp_path):
    cd = _setup(tmp_path)
    res = vn.apply_summary(cd, {"customer_name": "처음오심", "summary": "x", "tags": []})
    assert res["matched"] is False


def test_summarize_prompt_has_schema_and_transcript():
    p = vn.summarize_prompt("오늘 김문규님 다운펌")
    assert "customer_name" in p and "김문규" in p and "JSON" in p


from datetime import datetime

BOOKINGS = [
    {"date": "2026-06-26", "time": "14:00", "name": "김문규"},
    {"date": "2026-06-26", "time": "16:00", "name": "조희진"},
]


def test_match_by_time_picks_recent_appointment():
    # 16:30 녹음 → 직전 시작한 16:00(조희진)
    b = vn.match_by_time(datetime(2026, 6, 26, 16, 30), BOOKINGS)
    assert b["name"] == "조희진"
    # 14:40 녹음 → 14:00(김문규)
    b2 = vn.match_by_time(datetime(2026, 6, 26, 14, 40), BOOKINGS)
    assert b2["name"] == "김문규"


def test_match_by_time_other_day_none():
    assert vn.match_by_time(datetime(2026, 6, 27, 14, 30), BOOKINGS) is None


def test_resolve_by_time_when_no_name():
    custs = [{"id": "k", "name": "김문규"}, {"id": "j", "name": "조희진"}]
    cust, method, note = vn.resolve_customer(
        {"customer_name": ""}, custs, BOOKINGS, datetime(2026, 6, 26, 16, 20))
    assert cust["id"] == "j" and method == "time"


def test_resolve_name_and_time_agree():
    custs = [{"id": "k", "name": "김문규"}, {"id": "j", "name": "조희진"}]
    cust, method, _ = vn.resolve_customer(
        {"customer_name": "조희진님"}, custs, BOOKINGS, datetime(2026, 6, 26, 16, 20))
    assert cust["id"] == "j" and method == "name+time"


def test_resolve_name_wins_on_conflict():
    custs = [{"id": "k", "name": "김문규"}, {"id": "j", "name": "조희진"}]
    cust, method, note = vn.resolve_customer(
        {"customer_name": "김문규"}, custs, BOOKINGS, datetime(2026, 6, 26, 16, 20))
    assert cust["id"] == "k" and "불일치" in method and "조희진" in note
