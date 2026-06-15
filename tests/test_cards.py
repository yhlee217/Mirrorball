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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
