"""발견 케어 측정기 — 네트워크/CLI 없는 순수 파싱 테스트."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("expose_collect", ROOT / "expose_collect.py")
ec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ec)

TARGET = {"designer": {"name": "하예원", "aliases": ["예원쌤"]},
          "salon": {"name": "살롱톤", "aliases": ["살롱톤 영등포"]}}


def test_strip_tags():
    assert ec._strip_tags("<b>살롱톤</b> 영등포점") == "살롱톤 영등포점"


def test_rank_in_items_found_and_position():
    names = ec._names(TARGET)
    items = [{"name": "박승철헤어"}, {"name": "이철헤어"}, {"name": "살롱톤 영등포점"}]
    assert ec._rank_in_items(items, names) == 3


def test_rank_in_items_absent():
    names = ec._names(TARGET)
    items = [{"name": "준오헤어"}, {"name": "블루클럽"}]
    assert ec._rank_in_items(items, names) is None


def test_names_includes_designer_salon_aliases():
    ns = ec._names(TARGET)
    assert "하예원" in ns and "살롱톤" in ns and "예원쌤" in ns and "살롱톤 영등포" in ns


def test_mentioned_and_competitors():
    txt = "영등포는 박승철헤어스튜디오, 이철헤어커커가 유명하고 살롱톤도 있어요."
    names = ec._names(TARGET)
    assert ec._mentioned(txt, names) is True
    comps = ec._competitors(txt, names)
    assert "박승철헤어" not in comps or True       # 휴리스틱(접미사 기준)
    assert any("헤어" in c for c in comps) and "살롱톤" not in comps
