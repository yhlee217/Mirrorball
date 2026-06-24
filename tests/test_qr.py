"""QR 생성 테스트 — qr.make_qr / make_card / for_designer."""

import pytest

qr = pytest.importorskip("qr")
pytest.importorskip("segno")


def test_make_qr_writes_svg(tmp_path):
    p = tmp_path / "q.svg"
    qr.make_qr("https://example.com/book", str(p))
    body = p.read_text(encoding="utf-8")
    assert body.lstrip().startswith("<?xml") or "<svg" in body
    assert "<svg" in body


def test_make_card_embeds_qr_and_title(tmp_path):
    p = tmp_path / "card.svg"
    qr.make_card("https://naver.me/x", str(p), title="살롱톤", caption="네이버 예약")
    body = p.read_text(encoding="utf-8")
    assert "살롱톤" in body and "네이버 예약" in body
    assert "data:image/svg+xml" in body          # QR 이미지 임베드
    assert "스캔하면" in body


def test_for_designer_generates_booking_and_profile(tmp_path):
    y = tmp_path / "d.yaml"
    y.write_text(
        "slug: demo\nsalon: 데모살롱\n"
        "booking_url: https://m.booking.naver.com/x\n"
        "site_url: https://demo.example/\n",
        encoding="utf-8",
    )
    made = qr.for_designer(str(y), dist=str(tmp_path / "dist"))
    names = {p.split("/")[-1] for p in made}
    assert "qr-booking.svg" in names and "qr-booking-card.svg" in names
    assert "qr-profile.svg" in names


def test_for_designer_no_urls_returns_empty(tmp_path):
    y = tmp_path / "d.yaml"
    y.write_text("slug: demo\nsalon: x\n", encoding="utf-8")
    assert qr.for_designer(str(y), dist=str(tmp_path / "dist")) == []
