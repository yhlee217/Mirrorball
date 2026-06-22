#!/usr/bin/env python3
"""자동 프로필/포트폴리오 카피 생성 엔진 (루프 엔지니어링 대상).

미용사가 던진 최소 입력(키워드·사실)을 받아, RAG 로 주입된 검증된 영업
원칙을 녹여 SEO·전환 최적화된 카피를 생성한다. 생성 프롬프트(prompts/copy.md.j2)가
루프가 깎아내는 핵심 표적이다.

사용:
    python copygen.py eval/golden_set.yaml balayage_gangnam_damage   # 한 케이스 생성
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import engines

DEFAULT_PROMPT = "prompts/copy.md.j2"


def resolve_rag(case: dict, kb_path: str | None = None, k: int = 3) -> tuple[list[str], list[str]]:
    """(원칙, 예시) 결정.

    - 케이스에 rag_principles 가 명시되면 그대로 쓰고 예시는 비움(골든셋 = 통제된 평가).
    - 없고 kb_path 면 RAG 검색: 검색된 엔트리의 principle + example(few-shot)을 함께 반환.
    """
    explicit = case.get("rag_principles") or []
    if explicit:
        return explicit, []
    if kb_path:
        import rag

        ents = rag.retrieve(case.get("input", {}), kb_path=kb_path, k=k)
        principles = [e["principle"] for e in ents]
        examples = [e["example"] for e in ents if e.get("example")]
        return principles, examples
    return [], []


def resolve_principles(case: dict, kb_path: str | None = None, k: int = 3) -> list[str]:
    """원칙만 반환(하위호환)."""
    return resolve_rag(case, kb_path, k)[0]


def render_prompt(case: dict, prompt_path: str = DEFAULT_PROMPT,
                  *, kb_path: str | None = None, k: int = 3) -> str:
    """case(input + rag_principles + must_include/must_not_claim)로 생성 프롬프트 렌더.

    rag_principles 가 없고 kb_path 가 주어지면 RAG 로 검색해 주입한다.
    """
    from jinja2 import Environment, FileSystemLoader

    tpl = Path(prompt_path)
    env = Environment(
        loader=FileSystemLoader(str(tpl.parent)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    ctx = dict(case.get("input", {}))
    principles, examples = resolve_rag(case, kb_path=kb_path, k=k)
    ctx["rag_principles"] = principles
    ctx["rag_examples"] = examples
    ctx["must_include"] = case.get("must_include", []) or []
    ctx["must_not_claim"] = case.get("must_not_claim", []) or []
    return env.get_template(tpl.name).render(**ctx)


def generate_copy(
    case: dict,
    *,
    provider: str | None = None,
    model: str | None = None,
    prompt_path: str = DEFAULT_PROMPT,
    kb_path: str | None = None,
    k: int = 3,
) -> str:
    """설정된 provider 로 카피 생성 (웹검색 OFF). kb_path 주면 RAG 자동 검색."""
    provider = provider or os.getenv("COPY_PROVIDER") or os.getenv("REPORT_PROVIDER") or "gemini"
    models = engines.resolve_models()
    model = model or os.getenv("COPY_MODEL") or models.get(provider) or ""
    prompt = render_prompt(case, prompt_path, kb_path=kb_path, k=k)
    return asyncio.run(engines.complete(provider, prompt, {provider: model})).strip()


def main() -> None:
    import yaml

    if len(sys.argv) != 3:
        raise SystemExit("사용법: python copygen.py eval/golden_set.yaml {case_id}")
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    data = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
    case = next((c for c in data["cases"] if c.get("id") == sys.argv[2]), None)
    if not case:
        raise SystemExit(f"case '{sys.argv[2]}' 없음")
    print(generate_copy(case))


if __name__ == "__main__":
    main()
