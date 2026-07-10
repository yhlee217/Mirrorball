"""import_profile_edits — 앱 '소개 편집' → designers/{slug}.yaml 역반영 회귀.

편집 가능한 필드만 반영하고 en·slug·display_name·knows_about·SEO 등은 보존.
빈/누락 필드는 원본 유지(실수 삭제 방지). {"profile":...} 래핑 해제. 필드 순서 보존.
그리고 앱에 싣는 필드(build_app.PROFILE_EDITABLE) = 되받는 필드(EDITABLE) 일치 보장.
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import import_profile_edits as ipe


def _profile():
    return {
        "slug": "hayewoni",
        "display_name": "Hayewoni",
        "korean_name": "하 예 원",
        "tagline": "옛 태그라인",
        "about": ["옛 소개 1", "옛 소개 2"],
        "specialties": [{"name": "레이어드컷", "desc": "옛 설명"},
                        {"name": "퍼스널이미지컨설팅", "desc": "옛 설명2", "signature": True}],
        "faq": [{"q": "질문1", "a": "답1"}],
        "booking_url": "https://old",
        "knows_about": ["레이어드컷"],
        "en": {"tagline": "old EN", "about": ["EN1"]},
    }


def test_updates_editable_fields():
    p = _profile()
    ipe.apply_edits(p, {"tagline": "새 태그라인", "booking_url": "https://new"})
    assert p["tagline"] == "새 태그라인"
    assert p["booking_url"] == "https://new"


def test_preserves_non_editable():
    p = _profile()
    ipe.apply_edits(p, {"tagline": "새"})
    assert p["slug"] == "hayewoni"
    assert p["display_name"] == "Hayewoni"
    assert p["knows_about"] == ["레이어드컷"]
    assert p["en"] == {"tagline": "old EN", "about": ["EN1"]}      # 영문 보존


def test_ignores_missing_and_empty():
    p = _profile()
    ipe.apply_edits(p, {"tagline": "", "about": [], "faq": None})
    assert p["tagline"] == "옛 태그라인"                            # 빈 문자열 → 보존
    assert p["about"] == ["옛 소개 1", "옛 소개 2"]
    assert p["faq"] == [{"q": "질문1", "a": "답1"}]


def test_replaces_lists_wholesale():
    p = _profile()
    ipe.apply_edits(p, {"about": ["새 소개"], "faq": [{"q": "새Q", "a": "새A"}]})
    assert p["about"] == ["새 소개"]
    assert p["faq"] == [{"q": "새Q", "a": "새A"}]


def test_specialties_signature_preserved_when_sent():
    p = _profile()
    edits = {"specialties": [{"name": "레이어드컷", "desc": "새 설명"},
                            {"name": "퍼스널이미지컨설팅", "desc": "새2", "signature": True}]}
    ipe.apply_edits(p, edits)
    assert p["specialties"][1]["signature"] is True
    assert p["specialties"][0]["desc"] == "새 설명"


def test_ignores_unknown_fields():
    p = _profile()
    ipe.apply_edits(p, {"slug": "HACKED", "display_name": "X", "tagline": "새"})
    assert p["slug"] == "hayewoni"                                 # 편집대상 아님 → 무시
    assert p["display_name"] == "Hayewoni"
    assert p["tagline"] == "새"


def test_load_edits_unwraps_profile(tmp_path):
    f = tmp_path / "e.json"
    f.write_text(json.dumps({"profile": {"tagline": "T"}, "ts": "x"}), encoding="utf-8")
    assert ipe.load_edits(f) == {"tagline": "T"}


def test_load_edits_plain(tmp_path):
    f = tmp_path / "e.json"
    f.write_text(json.dumps({"tagline": "T"}), encoding="utf-8")
    assert ipe.load_edits(f) == {"tagline": "T"}


def test_changed_fields():
    assert ipe.changed_fields({"tagline": "x", "about": [], "faq": [{"q": "a", "a": "b"}]}) == ["tagline", "faq"]


def test_field_order_preserved():
    p = _profile()
    ipe.apply_edits(p, {"tagline": "새"})
    dumped = yaml.safe_dump(p, allow_unicode=True, sort_keys=False)
    assert dumped.index("slug:") < dumped.index("tagline:")       # 원래 순서 유지


def test_editable_matches_build_app():
    import build_app
    assert set(build_app.PROFILE_EDITABLE) == set(ipe.EDITABLE)   # 싣는 필드 = 되받는 필드
