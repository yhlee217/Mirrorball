"""애프터케어 팁 테스트 — aftercare.tips_for / message_for."""

import aftercare


def test_perm_tips():
    t = aftercare.tips_for("레이어드펌")
    assert any("24~48시간" in x for x in t)


def test_color_tips():
    t = aftercare.tips_for("발레아주")
    assert any("색 빠짐" in x for x in t)


def test_cut_tips():
    t = aftercare.tips_for("단발컷")
    assert any("라인" in x for x in t)


def test_unknown_service_has_default():
    t = aftercare.tips_for("두피문신")
    assert len(t) == 1


def test_none_service():
    assert aftercare.tips_for(None)        # 비어있지 않은 기본값


def test_message_includes_name_and_service():
    m = aftercare.message_for("지우", "레이어드펌")
    assert "지우님" in m and "레이어드펌" in m and "·" in m
