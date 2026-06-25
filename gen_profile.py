#!/usr/bin/env python3
"""프로필 카피 자동 생성 — 얇은 brief(facts) → 발행용 프로필 카피.

서비스의 '심장': 디자이너가 준 사실 몇 개만으로, AI/검색 인용에 강한 프로필
카피(tagline·시술 설명·소개·FAQ·knows_about)를 KB 영업 원칙을 녹여 생성한다.

엔진(copygen)과 같은 RAG·프롬프트 계열을 재사용하되, 출력은 '구조화 YAML'.

사용법:
    python gen_profile.py designers/_briefs/{slug}.yaml          # 키 있으면 생성→designers/{slug}.yaml
    python gen_profile.py designers/_briefs/{slug}.yaml --prompt  # 프롬프트만 출력(Claude 로 생성)

brief 스키마(필수만): slug, display_name, korean_name, role, salon, region,
instagram, booking_url, photo_url, address, services[], facts[], (선택) audience,
must_not_claim[], site_url. → 생성 결과 + brief 의 정적 필드를 합쳐 디자이너 yaml 완성.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

import rag

PROMPT = Path(__file__).parent / "prompts" / "profile_copy.md.j2"

# RAG 검색에 쓰는 상황 신호어(업종 중립이 아니라 헤어 기본값) — 복제 시 brief 의
# signal_keywords 로 덮어쓰거나 이 상수만 교체. (예: 네일=연장/오프/큐티클/속눈썹=리프트)
DEFAULT_SIGNAL_KEYWORDS = ["유지", "손상", "첫 방문", "리터치", "볼륨"]

# brief 에서 그대로 디자이너 yaml 로 넘어가는 정적 필드
_PASSTHROUGH = ("slug", "display_name", "korean_name", "role", "salon",
                "instagram", "booking_url", "photo_url", "site_url",
                "address_locality", "address_region")


def load_brief(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def build_case(brief: dict) -> dict:
    """RAG 검색용 case_input: 시술·신호어를 facts/services 에서 모은다."""
    services = brief.get("services", []) or []
    fact_text = " ".join(brief.get("facts", []) or [])
    signals = brief.get("signal_keywords") or DEFAULT_SIGNAL_KEYWORDS
    return {
        "service": services[0] if services else "",
        "audience": brief.get("audience", ""),
        "keywords": services + [w for w in signals if w in fact_text],
    }


def render_prompt(brief: dict, kb_path: str | None = None, k: int = 4) -> str:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(PROMPT.parent)),
                      trim_blocks=True, lstrip_blocks=True)
    principles = rag.principles_for(build_case(brief),
                                    kb_path=kb_path or rag.DEFAULT_KB, k=k)
    return env.get_template(PROMPT.name).render(
        region=brief.get("region", ""),
        salon=brief.get("salon", ""),
        display_name=brief.get("display_name", ""),
        role=brief.get("role", ""),
        audience=brief.get("audience", ""),
        services=brief.get("services", []) or [],
        facts=brief.get("facts", []) or [],
        must_not_claim=brief.get("must_not_claim", []) or [],
        rag_principles=principles,
    )


def parse_copy(text: str) -> dict:
    """모델 응답에서 YAML 본문만 추출해 파싱(코드펜스 허용)."""
    t = text.strip()
    if "```" in t:
        import re
        m = re.search(r"```(?:ya?ml)?\s*(.*?)```", t, re.DOTALL)
        if m:
            t = m.group(1).strip()
    data = yaml.safe_load(t)
    if not isinstance(data, dict):
        raise ValueError("생성 결과가 YAML 매핑이 아닙니다")
    return data


def merge(brief: dict, copy: dict) -> dict:
    """brief 정적 필드 + 생성 카피 → 완성 디자이너 yaml dict."""
    out = {k: brief[k] for k in _PASSTHROUGH if k in brief}
    for k in ("tagline", "specialties", "about", "faq", "knows_about"):
        if copy.get(k) is not None:
            out[k] = copy[k]
    loc = brief.get("location") or {}
    if loc:
        out["location"] = loc
    if brief.get("portfolio_labels"):
        out["portfolio_labels"] = brief["portfolio_labels"]
    return out


def generate(brief: dict, provider: str | None = None,
             kb_path: str | None = None) -> dict:
    """LLM provider 로 카피 생성 후 brief 와 병합. 키 없으면 RuntimeError."""
    import asyncio

    import engines

    prompt = render_prompt(brief, kb_path=kb_path)
    provider = provider or os.getenv("COPY_PROVIDER") or os.getenv("REPORT_PROVIDER")
    if not provider or not engines.active_engines().get(provider):
        raise RuntimeError("LLM provider/키 없음 — --prompt 로 프롬프트를 받아 Claude 로 생성하세요.")
    models = engines.resolve_models()
    text = asyncio.run(engines.complete(provider, prompt, {provider: models.get(provider, "")}))
    return merge(brief, parse_copy(text))


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("사용법: python gen_profile.py designers/_briefs/{slug}.yaml [--prompt]")
        return 2
    brief = load_brief(args[0])
    if "--prompt" in args:
        print(render_prompt(brief))
        return 0
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    try:
        result = generate(brief)
    except RuntimeError as e:
        print(f"ℹ {e}")
        return 1
    out = Path("designers") / f"{brief['slug']}.yaml"
    out.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"✓ {out}  생성 완료 — build.py 로 발행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
