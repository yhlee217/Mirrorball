#!/usr/bin/env python3
"""QR 코드 생성 — 예약 링크·프로필 링크를 스캔용 SVG 로.

거울·카운터·명함·전단지·인스타에 붙여 "스캔하면 바로 예약/프로필".
순수 파이썬(segno) — 외부 의존성 없음. SVG 라 인쇄해도 안 깨짐.

사용법:
    python qr.py "https://..." -o out.svg                 # 임의 URL
    python qr.py --designer designers/{slug}.yaml          # 예약·프로필 QR + 인쇄 카드
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DARK = "#2A2622"
ACCENT = "#6E5B47"
PAPER = "#FCFAF6"


def make_qr(url: str, path: str, scale: int = 10, border: int = 3,
            dark: str = DARK, light: str = "#FFFFFF") -> str:
    import segno

    segno.make(url, error="m").save(path, scale=scale, border=border, dark=dark, light=light)
    return path


def _qr_data_uri(url: str, scale: int = 8, dark: str = DARK) -> str:
    import segno

    return segno.make(url, error="m").svg_data_uri(scale=scale, border=0, dark=dark)


def make_card(url: str, path: str, *, title: str, caption: str) -> str:
    """인쇄용 브랜드 카드 SVG — 매장명 + QR + 안내 문구."""
    qr_uri = _qr_data_uri(url)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="560" viewBox="0 0 420 560">
  <rect width="420" height="560" rx="28" fill="{PAPER}"/>
  <rect x="14" y="14" width="392" height="532" rx="20" fill="none" stroke="#E6DFD4" stroke-width="2"/>
  <text x="210" y="78" text-anchor="middle" font-family="Cormorant Garamond, Georgia, serif"
    font-size="34" font-weight="600" fill="{ACCENT}">{_esc(title)}</text>
  <text x="210" y="108" text-anchor="middle" font-family="Pretendard, sans-serif"
    font-size="14" fill="#8C8479">{_esc(caption)}</text>
  <image x="80" y="140" width="260" height="260" href="{qr_uri}"/>
  <rect x="110" y="430" width="200" height="46" rx="23" fill="{ACCENT}"/>
  <text x="210" y="459" text-anchor="middle" font-family="Pretendard, sans-serif"
    font-size="16" font-weight="700" fill="#fff">스캔하면 바로 이동</text>
  <text x="210" y="512" text-anchor="middle" font-family="Pretendard, sans-serif"
    font-size="12" fill="#B7AE9F">카메라로 QR을 비춰주세요</text>
</svg>
"""
    Path(path).write_text(svg, encoding="utf-8")
    return path


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def for_designer(yaml_path: str, dist: str = "dist") -> list[str]:
    """디자이너 yaml → 예약·프로필 QR + 인쇄 카드 생성. 생성 경로 리스트 반환."""
    import yaml

    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}
    slug = data.get("slug") or Path(yaml_path).stem
    salon = data.get("salon", "")
    out_dir = Path(dist) / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    made: list[str] = []

    booking = (data.get("booking_url") or "").strip()
    site = (data.get("site_url") or "").strip()
    if booking:
        made.append(make_qr(booking, str(out_dir / "qr-booking.svg")))
        made.append(make_card(booking, str(out_dir / "qr-booking-card.svg"),
                              title=salon or "예약", caption="네이버 예약 바로가기"))
    if site:
        made.append(make_qr(site, str(out_dir / "qr-profile.svg")))
        made.append(make_card(site, str(out_dir / "qr-profile-card.svg"),
                              title=salon or "프로필", caption="프로필·예약 보기"))
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description="QR 코드 SVG 생성")
    ap.add_argument("url", nargs="?", help="QR 로 만들 URL")
    ap.add_argument("-o", "--out", default="qr.svg")
    ap.add_argument("--designer", help="designers/{slug}.yaml → 예약·프로필 QR 세트")
    args = ap.parse_args()

    if args.designer:
        made = for_designer(args.designer)
        for p in made:
            print(f"✓ {p}")
        if not made:
            print("ℹ booking_url / site_url 이 없어 생성할 QR 이 없습니다.")
        return 0
    if not args.url:
        print("사용법: python qr.py \"https://...\" -o out.svg | --designer designers/{slug}.yaml")
        return 2
    make_qr(args.url, args.out)
    print(f"✓ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
