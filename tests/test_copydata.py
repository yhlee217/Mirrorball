"""업종 카피 단일소스(copydata/kb/copy.yaml) + 설정 시ーム 테스트."""

import copydata
import schema


def test_copy_yaml_has_benefit_and_aftercare():
    assert copydata.benefit().get("rules")
    assert copydata.aftercare().get("rules")
    assert copydata.business_type() == "HairSalon"      # 헤어 기본값


def test_drafts_aftercare_read_same_source():
    import aftercare
    import drafts
    # kb/copy.yaml 의 데이터로 동일 산출
    assert "손질이 편" in drafts._benefit("레이어드펌")
    assert any("색 빠짐" in t for t in aftercare.tips_for("발레아주"))


def test_schema_type_defaults_hairsalon():
    p = schema.person_ld({"salon": "x"})
    assert p["worksFor"]["@type"] == "HairSalon"


def test_schema_type_respects_business_type():
    p = schema.person_ld({"salon": "x", "business_type": "NailSalon"})
    assert p["worksFor"]["@type"] == "NailSalon"        # 복제 시 설정으로 교체 가능


def test_build_app_injects_config(tmp_path):
    import build_app
    cdir = tmp_path / "clients" / "demo"
    (cdir / "customers").mkdir(parents=True)
    (cdir / "config.yaml").write_text("slug: demo\ntoday: 2026-06-23\n", encoding="utf-8")
    (cdir / "customers" / "x.yaml").write_text("id: x\nname: 김\n", encoding="utf-8")
    build_app.build_one(str(cdir), dist=str(tmp_path / "out"))
    import json
    d = json.loads((tmp_path / "out" / "demo.json").read_text(encoding="utf-8"))
    assert d["config"]["aftercare"]["rules"]            # 앱 JS 가 쓰는 단일 소스 주입
    assert d["config"]["benefit"]["default"]
