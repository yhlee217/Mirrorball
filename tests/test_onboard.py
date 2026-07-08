"""디자이너 서비스 일괄 세팅 — 전문시술 도출·발견설정 생성(순수 로직) 테스트."""

import yaml

import onboard


def test_derive_specialties_excludes_generic():
    recs = ([{"service": "남자컷"}] * 5 + [{"service": "다운펌"}] * 3
            + [{"service": "뿌리염색"}] * 2 + [{"service": "기장추가"}] * 4
            + [{"service": "여자컷"}] * 6)
    specs = onboard.derive_specialties(recs)
    assert "다운펌" in specs and "뿌리염색" in specs          # 전문시술
    assert "남자컷" not in specs and "여자컷" not in specs and "기장추가" not in specs   # 범용 제외


def test_derive_strips_tail_token():
    specs = onboard.derive_specialties([{"service": "클리닉펌제"}] * 3)
    assert specs == ["클리닉펌"]                             # 접미 '제' 정리


def test_gen_questions_uses_region_and_specs():
    qs = onboard.gen_questions("영등포시장역", ["다운펌", "뿌리염색", "레이어드컷"])
    assert any("영등포시장역 다운펌" in q for q in qs)
    assert any("근처 미용실" in q for q in qs)


def test_bootstrap_target_creates_then_preserves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    made = onboard.bootstrap_target("x", "테스트원장", "살롱톤", "영등포시장역", ["다운펌", "뿌리염색"])
    assert made is True
    d = yaml.safe_load((tmp_path / "targets" / "x.yaml").read_text(encoding="utf-8"))
    assert d["region"] == "영등포시장역" and d["specialties"] == ["다운펌", "뿌리염색"]
    assert d["designer"]["name"] == "테스트원장" and d["questions"]
    # 이미 있으면 수동 우선(안 덮음)
    (tmp_path / "targets" / "x.yaml").write_text("designer:\n  name: 수동수정\n", encoding="utf-8")
    assert onboard.bootstrap_target("x", "테스트원장", "살롱톤", "영등포시장역", ["펌"]) is False
    assert "수동수정" in (tmp_path / "targets" / "x.yaml").read_text(encoding="utf-8")


def test_designer_slugs_skips_demo_and_needs_records(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for s in ["hayewoni", "주환원", "minji", "유림"]:
        (tmp_path / "clients" / s).mkdir(parents=True)
        (tmp_path / "clients" / s / "records.yaml").write_text("[]", encoding="utf-8")
    (tmp_path / "clients" / "noRecords").mkdir(parents=True)   # records 없음 → 제외
    got = set(onboard.designer_slugs())
    assert got == {"hayewoni", "주환원", "유림"}               # minji(데모)·noRecords 제외
