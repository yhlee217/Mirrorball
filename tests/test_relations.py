"""고객 관계 해석 테스트 — relations.resolve."""

import relations

CUSTOMERS = [
    {"id": "jiwoo", "name": "지우", "relations": [{"to": "park", "type": "친구"}]},
    {"id": "park", "name": "박○○", "relations": [{"to": "jiwoo", "type": "친구"}]},
    {"id": "lee", "name": "이○○", "referred_by": "park"},
    {"id": "noname"},  # id 만
]


def test_mutual_relation_resolved_with_name():
    r = relations.resolve(CUSTOMERS)
    assert r["jiwoo"]["relations"] == [{"id": "park", "name": "박○○", "type": "친구"}]


def test_referred_by_resolved():
    r = relations.resolve(CUSTOMERS)
    assert r["lee"]["referred_by"] == {"id": "park", "name": "박○○"}


def test_referred_reverse_computed():
    r = relations.resolve(CUSTOMERS)
    # 박○○ 가 이○○ 를 소개 → referred 역산
    assert r["park"]["referred"] == [{"id": "lee", "name": "이○○"}]
    assert r["jiwoo"]["referred"] == []


def test_unknown_referrer_dropped():
    r = relations.resolve([{"id": "a", "name": "A", "referred_by": "ghost"}])
    assert r["a"]["referred_by"] is None       # 존재하지 않는 소개자는 무시


def test_type_default():
    r = relations.resolve([
        {"id": "a", "name": "A", "relations": [{"to": "b"}]},
        {"id": "b", "name": "B"},
    ])
    assert r["a"]["relations"][0]["type"] == "지인"


def test_build_app_includes_relations(tmp_path):
    import build_app
    cdir = tmp_path / "clients" / "demo"
    (cdir / "customers").mkdir(parents=True)
    (cdir / "config.yaml").write_text("slug: demo\ntoday: 2026-06-23\n", encoding="utf-8")
    (cdir / "customers" / "a.yaml").write_text(
        "id: a\nname: 가\nrelations:\n  - to: b\n    type: 자매\n", encoding="utf-8")
    (cdir / "customers" / "b.yaml").write_text(
        "id: b\nname: 나\nreferred_by: a\n", encoding="utf-8")
    build_app.build_one(str(cdir), dist=str(tmp_path / "out"))
    import json
    d = json.loads((tmp_path / "out" / "demo.json").read_text(encoding="utf-8"))
    by = {c["id"]: c for c in d["clients"]}
    assert by["a"]["relations"][0]["type"] == "자매"
    assert by["a"]["referred"][0]["name"] == "나"     # a 가 b 를 소개
    assert by["b"]["referred_by"]["name"] == "가"
