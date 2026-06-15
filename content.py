#!/usr/bin/env python3
"""인용 가능한 콘텐츠 초안 생성 — designers/{slug}.yaml 의 데이터로
네이버 블로그·플레이스에 올릴 글을 설정된 provider 로 생성한다.

사용법:
    python content.py designers/minji.yaml

진단 결과의 1순위 개선점("AI가 인용할 글이 없음")을 채우는 도구.
프롬프트는 코드에 하드코딩하지 않고 prompts/content.md.j2 로 분리.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import yaml

import engines

DEFAULT_TEMPLATE = "prompts/content.md.j2"


def load_data(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def render_prompt(data: dict, template_path: str = DEFAULT_TEMPLATE) -> str:
    from jinja2 import Environment, FileSystemLoader

    tpl = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(tpl.parent)),
        autoescape=False,            # 프롬프트(HTML 아님)
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(tpl.name).render(**data)


def generate_content(
    data: dict,
    *,
    provider: str | None = None,
    model: str | None = None,
    template_path: str = DEFAULT_TEMPLATE,
) -> str:
    """설정된 provider 로 콘텐츠 초안 마크다운 생성 (웹검색 OFF)."""
    provider = provider or os.getenv("REPORT_PROVIDER") or "gemini"
    models = engines.resolve_models()
    model = model or os.getenv("REPORT_MODEL") or models.get(provider) or ""
    prompt = render_prompt(data, template_path)
    text = asyncio.run(engines.complete(provider, prompt, {provider: model}))
    return text.strip()


def write_content(markdown: str, slug: str, out_dir: str = "content") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{slug}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python content.py designers/{slug}.yaml")

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    data = load_data(sys.argv[1])
    if not data or not data.get("specialties") or not data.get("faq"):
        raise SystemExit("specialties / faq 가 있어야 콘텐츠를 만들 수 있습니다")
    slug = data.get("slug") or Path(sys.argv[1]).stem

    provider = os.getenv("REPORT_PROVIDER") or "gemini"
    print(f"콘텐츠 생성 중... (provider: {provider})")
    markdown = generate_content(data)
    path = write_content(markdown, slug)
    print(f"콘텐츠 저장: {path}")


if __name__ == "__main__":
    main()
