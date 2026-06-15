"""cards.py — 손님용 카드 생성 (mock data, 네트워크 없음)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import cards  # noqa: E402

AFTERCARE = {
    "type": "aftercare",
    "designer": "하예원",
    "salon": "꼼나나비앙 한남점",
    "customer": "지우",
    "service": "레이어드펌",
    "service_date": "6월 11일",
    "tips": [
        {"icon": "💧", "title": "3일간 샴푸 피하기", "desc": "펌이 자리잡아요"},
        {"icon": "✨", "title": "트리트먼트", "desc": "유지력 ↑"},
    ],
    "next_visit": "11월 초",
    "remind": True,
    "booking_url": "https://book/x",
}


def test_aftercare_renders():
    html = cards.render(AFTERCARE)
    assert "지우 님 레이어드펌 관리" in html
    assert "하예원 · 꼼나나비앙 한남점 · 6월 11일 시술" in html
    assert html.count('class="row"') == 2          # tip 2개
    assert "3일간 샴푸 피하기" in html
    assert "다음 방문 추천: <b>11월 초</b>" in html
    assert '안부 메시지로 알려드릴게요' in html      # remind=true
    assert 'href="https://book/x"' in html          # 예약 버튼


def test_aftercare_optional_fields_absent():
    d = {k: v for k, v in AFTERCARE.items()
         if k not in ("next_visit", "remind", "booking_url", "service_date")}
    html = cards.render(d)
    assert "다음 방문 추천" not in html
    assert "예약하기" not in html
    assert "시술" not in html.split("</div>")[3]  # service_date 없으면 표기 안 함


def test_render_unknown_type_raises():
    with pytest.raises(ValueError):
        cards.render({"type": "nope", "designer": "x", "customer": "y"})


def test_render_requires_designer_customer():
    with pytest.raises(ValueError):
        cards.render({"type": "aftercare", "designer": "x"})  # customer 없음


def test_build_one_writes(tmp_path):
    import yaml

    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(dict(AFTERCARE, name="c"), allow_unicode=True), encoding="utf-8")
    out = cards.build_one(str(p), dist=str(tmp_path / "dist"))
    assert out.exists() and "지우" in out.read_text(encoding="utf-8")


def test_build_one_real_example(tmp_path):
    out = cards.build_one("cards/example_aftercare.yaml", dist=str(tmp_path / "dist"))
    assert out.name == "jiu_aftercare.html" and out.exists()


# --- 스타일 카드 ------------------------------------------------------------
STYLE = {
    "type": "style", "designer": "하예원", "salon": "꼼나나비앙 한남점", "customer": "지우",
    "face_shape": "계란형", "face_note": "레이어드컷이 잘 어울려요",
    "recommended": ["레이어드컷", "레이어드펌"], "recommended_note": "자연스러운 흐름",
    "personal_color": "가을 웜", "swatches": ["#B5754A", "#8C6A3E"],
    "comment": "단발도 잘 어울려요", "booking_url": "https://book/x",
}


def test_style_card_renders():
    html = cards.render(STYLE)
    assert "지우 님의 스타일" in html and "by 하예원" in html
    assert "계란형" in html and "레이어드컷이 잘 어울려요" in html
    assert "레이어드컷 · 레이어드펌" in html          # join
    assert html.count('class="sw"') == 1
    assert "background:#B5754A" in html and html.count('<span style="background:') == 2
    assert 'href="https://book/x"' in html


def test_style_card_optional_absent():
    html = cards.render({"type": "style", "designer": "x", "salon": "s", "customer": "y"})
    assert "얼굴형" not in html and "퍼스널컬러" not in html and "예약하기" not in html


# --- 예약 확정 카드 ---------------------------------------------------------
BOOKING = {
    "type": "booking", "designer": "하예원", "salon": "꼼나나비앙 한남점", "customer": "지우",
    "when": "6월 18일 오후 2시", "service": "레이어드펌", "duration": "약 2시간 반",
    "directions": "이태원역 택시", "prep": "가볍게 감고 오세요",
    "calendar_url": "https://cal/x", "map_url": "https://map/x",
}


def test_booking_card_renders():
    html = cards.render(BOOKING)
    assert "예약이 확정됐어요" in html
    assert "6월 18일 오후 2시" in html
    assert "레이어드펌 · 약 2시간 반" in html
    assert "이태원역 택시" in html and "가볍게 감고 오세요" in html
    assert 'href="https://cal/x"' in html and 'href="https://map/x"' in html


def test_booking_card_optional_absent():
    html = cards.render({"type": "booking", "designer": "x", "salon": "s", "customer": "y"})
    assert '<div class="twobtn">' not in html  # 버튼 url 없으면 버튼줄 요소 없음
    assert '<div class="prep">' not in html    # prep 없으면 안내 박스 없음


# --- 친구 소개 / 단골 적립 카드 --------------------------------------------
def test_referral_card_renders():
    html = cards.render({"type": "referral", "designer": "하예원", "salon": "s", "customer": "지우",
                         "offer": "둘 다 20% 할인", "code": "HAYE·지우", "share_url": "https://s/x"})
    assert "지우 님이 친구를 소개하면" in html and "둘 다 20% 할인" in html
    assert "HAYE·지우" in html
    assert 'href="https://s/x"' in html


def test_loyalty_card_stamps():
    html = cards.render({"type": "loyalty", "designer": "하예원", "salon": "s", "customer": "지우",
                         "total": 10, "stamps": 4, "goal": 6, "reward": "트리트먼트 무료"})
    assert html.count('class="st on"') == 4       # 채워진 도장 4
    assert html.count('class="st off"') == 6      # 빈 칸 6
    assert "현재 <b>4개</b>" in html
    assert "2번 더 오시면 트리트먼트 무료" in html   # goal-stamps = 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
