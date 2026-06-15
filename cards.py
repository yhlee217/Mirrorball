#!/usr/bin/env python3
"""손님용 카드 생성기 — 시술 후 보내는 공유 카드(정적 HTML).

사용법:
    python cards.py cards/jiu_aftercare.yaml      # 한 장
    python cards.py --all                          # cards/*.yaml 전부

입력(cards/{name}.yaml)은 type 으로 카드 종류를 고른다. 출력은 순수 정적
HTML (dist/cards/{name}.html) — 손님에게 링크로 보내거나 캡처해서 공유.
새 카드 종류는 templates/cards/{type}.html.j2 만 추가하면 된다.
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import yaml

TEMPLATE_DIR = Path(__file__).parent / "templates" / "cards"
# type -> 템플릿 파일
TYPES = {
    "aftercare": "aftercare.html.j2",
    "style": "style.html.j2",
    "booking": "booking.html.j2",
}


def load_data(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _env():
    from jinja2 import Environment, FileSystemLoader

    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(data: dict) -> str:
    t = data.get("type")
    if t not in TYPES:
        raise ValueError(f"알 수 없는 카드 type: {t!r} (가능: {', '.join(TYPES)})")
    for key in ("designer", "customer"):
        if not data.get(key):
            raise ValueError(f"카드에 {key} 가 필요합니다")
    return _env().get_template(TYPES[t]).render(**data)


def build_one(path: str, dist: str = "dist") -> Path:
    data = load_data(path)
    name = data.get("name") or Path(path).stem
    html = render(data)
    out = Path(dist) / "cards" / f"{name}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit("사용법: python cards.py cards/{name}.yaml | --all")
    paths = sorted(glob.glob("cards/*.yaml")) if args[0] == "--all" else [args[0]]
    if not paths:
        raise SystemExit("cards/*.yaml 이 없습니다")

    for p in paths:
        try:
            out = build_one(p)
            print(f"✓ {out}")
        except Exception as exc:
            print(f"✗ {p}: {exc}")


if __name__ == "__main__":
    main()
