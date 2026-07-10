"""import_app_edits — 앱 편집(수동필드) → 카르테 역동기화 계약 테스트.

핵심 계약:
  · 앱의 수동필드(생일·메모 등)가 기존 카르테에 반영된다.
  · 거래 필드(이력·매출)는 앱 값이 뭐든 YAML(HandSOS) 값이 유지된다.
  · 빈 앱값은 기존값을 지우지 않는다(무-덮어쓰기).
  · 변화 없으면 갱신 대상에 안 들어간다(불필요한 재기록 방지).
  · 매칭 YAML 없는(앱 추가) 고객은 unmatched → app_added.yaml.
  · import_handsos 와 동일한 _MANUAL_FIELDS 를 쓴다(드리프트 방지).
"""

import json

import yaml

import import_app_edits as iae
from import_handsos import _MANUAL_FIELDS


def _mk(client_dir, cid, data):
    d = client_dir / "customers"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cid}.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_birthday_synced_transactional_preserved(tmp_path):
    cd = tmp_path / "clients" / "hayewoni"
    _mk(cd, "c5120", {"id": "c5120", "name": "배상웅", "custno": "5120",
                      "history": [{"date": "2026-06-26", "service": "컷"}], "total_won": 120000})
    # 앱: 생일 입력 + (거래 필드는 낡은 값이어도 무시돼야)
    app = [{"id": "c5120", "name": "배상웅", "birthday": "06-26", "history": [], "total_won": 0}]
    updates, unmatched = iae.apply_edits(cd, app)
    assert unmatched == []
    assert len(updates) == 1
    _, merged = updates[0]
    assert merged["birthday"] == "06-26"                                  # 수동 반영
    assert merged["history"] == [{"date": "2026-06-26", "service": "컷"}]  # 거래 유지
    assert merged["total_won"] == 120000


def test_empty_app_field_does_not_wipe(tmp_path):
    cd = tmp_path / "clients" / "s"
    _mk(cd, "c1", {"id": "c1", "name": "A", "custno": "1", "birthday": "12-25"})
    updates, unmatched = iae.apply_edits(cd, [{"id": "c1", "name": "A", "birthday": ""}])
    assert updates == []          # 빈값이 12-25 를 안 지움 → 변화 없음


def test_app_manual_wins_over_yaml(tmp_path):
    cd = tmp_path / "clients" / "s"
    _mk(cd, "c1", {"id": "c1", "name": "A", "custno": "1", "memo": "예전메모"})
    updates, _ = iae.apply_edits(cd, [{"id": "c1", "name": "A", "memo": "새메모"}])
    assert len(updates) == 1
    assert updates[0][1]["memo"] == "새메모"


def test_no_change_no_update(tmp_path):
    cd = tmp_path / "clients" / "s"
    _mk(cd, "c1", {"id": "c1", "name": "A", "custno": "1", "birthday": "03-03"})
    updates, unmatched = iae.apply_edits(cd, [{"id": "c1", "name": "A", "birthday": "03-03"}])
    assert updates == [] and unmatched == []      # 동일 → 재기록 안 함


def test_unmatched_app_added(tmp_path):
    cd = tmp_path / "clients" / "s"
    _mk(cd, "c1", {"id": "c1", "name": "A", "custno": "1"})
    app = [{"id": "c1", "name": "A", "memo": "단골"},
           {"id": "u_new", "name": "신규손님", "birthday": "05-05"}]
    updates, unmatched = iae.apply_edits(cd, app)
    assert len(updates) == 1
    assert len(unmatched) == 1 and unmatched[0]["id"] == "u_new"
    slim = iae.slim_for_review(unmatched)
    assert slim == [{"id": "u_new", "name": "신규손님", "birthday": "05-05"}]  # 거래·PII 없이 수동만


def test_relations_and_prefer_synced(tmp_path):
    cd = tmp_path / "clients" / "s"
    _mk(cd, "c1", {"id": "c1", "name": "A", "custno": "1", "history": [{"date": "2026-01-01"}]})
    app = [{"id": "c1", "name": "A", "prefer": ["레이어드컷"],
            "relations": [{"to": "c2", "type": "가족"}]}]
    updates, _ = iae.apply_edits(cd, app)
    _, merged = updates[0]
    assert merged["prefer"] == ["레이어드컷"]
    assert merged["relations"] == [{"to": "c2", "type": "가족"}]
    assert merged["history"] == [{"date": "2026-01-01"}]      # 거래 유지


def test_load_app_export_forms(tmp_path):
    arr = tmp_path / "a.json"
    arr.write_text(json.dumps([{"id": "c1"}]), encoding="utf-8")
    assert iae.load_app_export(str(arr)) == [{"id": "c1"}]
    obj = tmp_path / "b.json"
    obj.write_text(json.dumps({"customers": [{"id": "c2"}]}), encoding="utf-8")
    assert iae.load_app_export(str(obj)) == [{"id": "c2"}]


def test_uses_pipeline_manual_fields():
    # 파이프라인과 동일한 수동필드 집합을 참조(드리프트 방지)
    assert "birthday" in _MANUAL_FIELDS and "memo" in _MANUAL_FIELDS
