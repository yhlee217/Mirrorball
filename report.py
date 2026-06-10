"""raw.json -> Jinja2 프롬프트 -> 설정된 provider -> report.md

리포트 LLM 은 REPORT_PROVIDER(기본 gemini)/REPORT_MODEL 로 .env 에서 지정한다.
리포트 프롬프트는 코드에 하드코딩하지 않고 prompts/report.md.j2 로 분리한다.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path

import engines
from extract import domain_of

DEFAULT_TEMPLATE = "prompts/report.md.j2"
ENGINE_LABELS = {"openai": "ChatGPT", "gemini": "Gemini", "perplexity": "Perplexity"}


def load_raw(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _aggregate(raw: dict) -> dict:
    """레코드를 리포트용으로 집계. 엔진 컬럼은 실제 등장한(활성) 엔진만."""
    records = raw.get("records", [])

    engines_used: list[str] = []
    for r in records:
        if r["engine"] not in engines_used:
            engines_used.append(r["engine"])

    questions: list[str] = []
    for r in records:
        if r["question"] not in questions:
            questions.append(r["question"])

    rows = []
    total_mentions = 0
    domain_counter: Counter[str] = Counter()
    competitor_counter: Counter[str] = Counter()
    success = 0
    failed = 0

    for q in questions:
        row = {"question": q, "engines": {}}
        for eng in engines_used:
            samples = [r for r in records if r["question"] == q and r["engine"] == eng]
            mentioned_n = sum(1 for r in samples if (r.get("extraction") or {}).get("mentioned"))
            context = next(
                (r["extraction"]["context"] for r in samples
                 if (r.get("extraction") or {}).get("context")),
                None,
            )
            row["engines"][eng] = {
                "label": ENGINE_LABELS.get(eng, eng),
                "mentioned": mentioned_n > 0,
                "ratio": f"{mentioned_n}/{len(samples)}" if samples else "0/0",
                "context": context,
            }
        rows.append(row)

    for r in records:
        if r.get("error"):
            failed += 1
            continue
        success += 1
        ext = r.get("extraction") or {}
        if ext.get("mentioned"):
            total_mentions += 1
        for url in ext.get("citations", []):
            d = domain_of(url)
            if d:
                domain_counter[d] += 1
        for c in ext.get("competitors_mentioned", []):
            competitor_counter[c] += 1

    return {
        "designer": raw.get("designer", {}),
        "salon": raw.get("salon", {}),
        "region": raw.get("region", ""),
        "specialties": raw.get("specialties", []),
        "sampling": raw.get("sampling", 1),
        "run_at": raw.get("run_at", ""),
        "models": raw.get("models", {}),
        "engines_used": engines_used,
        "engine_labels": {e: ENGINE_LABELS.get(e, e) for e in engines_used},
        "questions": questions,
        "rows": rows,
        "total_mentions": total_mentions,
        "total_calls": len(records),
        "success": success,
        "failed": failed,
        "domains": domain_counter.most_common(),
        "competitors": competitor_counter.most_common(),
    }


def render_prompt(raw: dict, template_path: str = DEFAULT_TEMPLATE) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    tpl_path = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(tpl_path.parent)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(tpl_path.name)
    return template.render(**_aggregate(raw))


def generate_report(
    raw: dict,
    *,
    provider: str | None = None,
    model: str | None = None,
    template_path: str = DEFAULT_TEMPLATE,
) -> str:
    """설정된 provider 로 고객 전달용 마크다운 리포트 생성."""
    provider = provider or os.getenv("REPORT_PROVIDER") or "gemini"
    models = engines.resolve_models()
    model = model or os.getenv("REPORT_MODEL") or models.get(provider) or ""
    prompt = render_prompt(raw, template_path)

    text = asyncio.run(engines.complete(provider, prompt, {provider: model}))
    return text.strip()


def write_report(markdown: str, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.md"
    path.write_text(markdown, encoding="utf-8")
    return path
