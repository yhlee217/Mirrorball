#!/usr/bin/env python3
"""자율 루프 드라이버 — 사람 개입 없이 카피 프롬프트를 스스로 개선한다.

루프: baseline → 최약축 진단 → (LLM 엔지니어가) prompts/copy.md.j2 한 갈래 수정
      → 재채점 → 총점 오르고 회귀 없으면 채택, 아니면 롤백 → 정지(전부 pass | 플래토).

제어 로직(better/passed/run)은 LLM 없이 테스트된다. 실제 실행엔 .env 키 필요:
    python run_loop.py            # prompts/copy.md.j2 를 자기개선
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import eval_loop

COPY_PROMPT = "prompts/copy.md.j2"
ENGINEER_PROMPT = "prompts/engineer.md.j2"
AXES = eval_loop.AXES


# --- 순수 제어 로직 (LLM 없이 테스트 가능) ---------------------------------
def passed(agg: dict) -> bool:
    """모든 케이스가 전 축 통과(= aggregate.pass == total)."""
    return agg.get("total", 0) > 0 and agg["pass"] == agg["total"]


def better(new: dict, old: dict, tol: float = 0.0) -> bool:
    """총점이 오르고 어떤 축도 tol 이상 회귀하지 않으면 개선으로 채택."""
    if new["overall"] <= old["overall"]:
        return False
    for a in AXES:
        if new["axis_mean"].get(a, 0) < old["axis_mean"].get(a, 0) - tol:
            return False
    return True


def collect_failures(results: list[dict], limit: int = 6) -> list[dict]:
    out = []
    for r in results:
        for f in r["verdict"].get("failures", []) or []:
            out.append(f)
            if len(out) >= limit:
                return out
    return out


# --- 루프 (evaluate / propose 주입 가능 → 테스트는 mock, 실전은 LLM) --------
def run(
    prompt_path: str = COPY_PROMPT,
    golden: list[dict] | None = None,
    *,
    max_iters: int = 6,
    patience: int = 3,
    tol: float = 0.0,
    evaluate=None,
    propose=None,
    write_back: bool = True,
) -> dict:
    golden = golden if golden is not None else eval_loop.load_golden()
    evaluate = evaluate or _evaluate_default(golden)
    propose = propose or _propose_default()

    current = Path(prompt_path).read_text(encoding="utf-8")
    best_agg, best_results = evaluate(current)
    log = [{"iter": 0, "action": "baseline",
            "overall": best_agg["overall"], "weakest": best_agg["weakest_axis"],
            "pass": f'{best_agg["pass"]}/{best_agg["total"]}'}]

    no_improve = 0
    for i in range(1, max_iters + 1):
        if passed(best_agg):
            log.append({"iter": i, "action": "stop_all_pass"})
            break
        candidate = propose(current, best_agg, best_results)
        cand_agg, cand_results = evaluate(candidate)
        if better(cand_agg, best_agg, tol):
            current, best_agg, best_results = candidate, cand_agg, cand_results
            no_improve = 0
            action = "accept"
        else:
            no_improve += 1
            action = "rollback"
        log.append({"iter": i, "action": action,
                    "overall": cand_agg["overall"], "weakest": cand_agg["weakest_axis"]})
        if no_improve >= patience:
            log.append({"iter": i, "action": "stop_plateau"})
            break

    if write_back:
        Path(prompt_path).write_text(current, encoding="utf-8")
    return {"final_prompt": current, "aggregate": best_agg, "log": log}


# --- 실전 구현 (LLM) -------------------------------------------------------
def _evaluate_default(golden):
    """프롬프트 텍스트를 받아 golden 전체를 생성·채점 → (aggregate, results)."""
    def evaluate(prompt_text: str):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "copy_candidate.md.j2"
            p.write_text(prompt_text, encoding="utf-8")
            out = eval_loop.run_baseline(golden, gen_kwargs={"prompt_path": str(p)})
        return out["aggregate"], out["results"]
    return evaluate


def _propose_default():
    """LLM 엔지니어가 현재 프롬프트를 한 갈래 개선한 전체 프롬프트를 반환."""
    import asyncio

    import engines

    def propose(current_prompt: str, agg: dict, results: list[dict]) -> str:
        from jinja2 import Environment, FileSystemLoader

        tpl = Path(ENGINEER_PROMPT)
        env = Environment(loader=FileSystemLoader(str(tpl.parent)),
                          autoescape=False, trim_blocks=True, lstrip_blocks=True)
        prompt = env.get_template(tpl.name).render(
            current_prompt=current_prompt,
            axis_mean=agg["axis_mean"],
            weakest_axis=agg["weakest_axis"],
            failures=collect_failures(results),
        )
        provider = os.getenv("ENGINEER_PROVIDER") or os.getenv("COPY_PROVIDER") or "gemini"
        model = os.getenv("ENGINEER_MODEL") or engines.resolve_models().get(provider) or ""
        return asyncio.run(engines.complete(provider, prompt, {provider: model})).strip()
    return propose


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    out = run()
    print("=== loop ===")
    for e in out["log"]:
        extra = f" overall={e.get('overall')} weakest={e.get('weakest')}" if "overall" in e else ""
        print(f"  iter {e['iter']:>2} · {e['action']}{extra}")
    a = out["aggregate"]
    print(f"\n최종 종합 {a['overall']} · pass {a['pass']}/{a['total']} · 축 {a['axis_mean']}")


if __name__ == "__main__":
    main()
