#!/usr/bin/env python3
"""카피 엔진 루프 하니스 — baseline 채점 · 평가 · 집계.

흐름: golden_set.input → copygen.generate_copy → judge(LLM, 다른 모델) →
루브릭 점수(JSON) → 집계(축 평균·최약축·pass). 루프의 코드 변경/채택은
eval/LOOP_PROMPT.md 의 지시문대로 AI 에이전트가 이 하니스를 돌려 수행한다.

사용:
    python eval_loop.py            # golden_set 전체 baseline 채점 리포트
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import engines
import copygen

JUDGE_PROMPT = "prompts/judge.md.j2"
GOLDEN = "eval/golden_set.yaml"
AXES = ("A", "B", "C", "D", "E")
PASS_THRESHOLD = 4.5


def load_golden(path: str = GOLDEN) -> list[dict]:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [c for c in data.get("cases", []) if not str(c.get("id", "")).startswith("TEMPLATE")]


def parse_judge(text: str) -> dict:
    """LLM 출력에서 첫 JSON 객체를 견고하게 추출(코드펜스·프롤로그 무시)."""
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1 or e < s:
        raise ValueError("judge 출력에 JSON 객체가 없습니다")
    return json.loads(text[s:e + 1])


def _render_judge(case: dict, generated: str, prompt_path: str = JUDGE_PROMPT) -> str:
    from jinja2 import Environment, FileSystemLoader

    inp = case.get("input", {})
    ctx = {
        "generated": generated,
        "facts": inp.get("facts", []) or [],
        "service": inp.get("service", ""),
        "region": inp.get("region", ""),
        "rag_principles": case.get("rag_principles", []) or [],
        "must_include": case.get("must_include", []) or [],
        "must_not_claim": case.get("must_not_claim", []) or [],
        "reference_output": case.get("reference_output", ""),
    }
    tpl = Path(prompt_path)
    env = Environment(
        loader=FileSystemLoader(str(tpl.parent)),
        autoescape=False, trim_blocks=True, lstrip_blocks=True,
    )
    return env.get_template(tpl.name).render(**ctx)


def judge(case: dict, generated: str, *, provider: str | None = None,
          model: str | None = None, prompt_path: str = JUDGE_PROMPT) -> dict:
    # 평가자는 생성기와 '다른 모델'을 권장(자기편향 ↓) → JUDGE_PROVIDER
    provider = provider or os.getenv("JUDGE_PROVIDER") or "gemini"
    models = engines.resolve_models()
    model = model or os.getenv("JUDGE_MODEL") or models.get(provider) or ""
    prompt = _render_judge(case, generated, prompt_path)
    raw = asyncio.run(engines.complete(provider, prompt, {provider: model}))
    return parse_judge(raw)


# --- 순수 채점 로직 (LLM 없이 테스트 가능) ---------------------------------
def case_overall(verdict: dict) -> float:
    """가드레일 위반이면 0, 아니면 5축 평균."""
    if verdict.get("guardrail_violations"):
        return 0.0
    sc = verdict.get("scores", {})
    vals = [float(sc.get(a, 0)) for a in AXES]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def case_pass(verdict: dict) -> bool:
    if verdict.get("guardrail_violations"):
        return False
    sc = verdict.get("scores", {})
    return all(float(sc.get(a, 0)) >= PASS_THRESHOLD for a in AXES)


def aggregate(results: list[dict]) -> dict:
    """results: [{id, verdict}] → 축 평균·종합·pass·최약축."""
    per_axis = {a: [] for a in AXES}
    overalls, passes = [], 0
    for r in results:
        v = r["verdict"]
        sc = v.get("scores", {})
        for a in AXES:
            per_axis[a].append(float(sc.get(a, 0)))
        overalls.append(case_overall(v))
        passes += 1 if case_pass(v) else 0
    axis_mean = {a: round(sum(x) / len(x), 2) if x else 0.0 for a, x in per_axis.items()}
    weakest = min(axis_mean, key=axis_mean.get) if axis_mean else None
    return {
        "axis_mean": axis_mean,
        "overall": round(sum(overalls) / len(overalls), 2) if overalls else 0.0,
        "pass": passes,
        "total": len(results),
        "weakest_axis": weakest,
    }


def score_case(case: dict, *, gen_kwargs: dict | None = None,
               judge_kwargs: dict | None = None) -> dict:
    generated = copygen.generate_copy(case, **(gen_kwargs or {}))
    verdict = judge(case, generated, **(judge_kwargs or {}))
    return {"id": case["id"], "generated": generated, "verdict": verdict}


def run_baseline(golden: list[dict] | None = None, **kw) -> dict:
    golden = golden if golden is not None else load_golden()
    results = [score_case(c, **kw) for c in golden]
    return {"results": results, "aggregate": aggregate(results)}


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    out = run_baseline()
    print("=== baseline ===")
    for r in out["results"]:
        v = r["verdict"]
        print(f"- {r['id']}: overall {case_overall(v)}  pass={case_pass(v)}  "
              f"최약축={v.get('weakest_axis')}")
    a = out["aggregate"]
    print(f"\n축 평균: {a['axis_mean']}")
    print(f"종합 {a['overall']} · pass {a['pass']}/{a['total']} · 최약축 {a['weakest_axis']}")


if __name__ == "__main__":
    main()
