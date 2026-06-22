"""카피 엔진 루프 하니스 — copygen + eval_loop. LLM 없이 mock 으로 검증."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import copygen  # noqa: E402
import engines  # noqa: E402
import eval_loop  # noqa: E402

CASE = {
    "id": "c1",
    "input": {
        "region": "강남역", "salon": "살롱드헤어", "designer": "민지", "service": "발레아주",
        "facts": ["손상 최소화 펌제", "4주 뒤에도 자연스러움"],
        "audience": "뿌리 자람 걱정 고객",
    },
    "rag_principles": ["재방문 시점을 카피에 각인", "첫 방문은 상담으로 전환"],
    "must_include": ["강남", "발레아주"],
    "must_not_claim": ["연예인", "1위"],
    "reference_output": "강남역 발레아주 정답 카피...",
}


def _verdict(a, b, c, d, e, guardrail=None):
    return {"scores": {"A": a, "B": b, "C": c, "D": d, "E": e},
            "guardrail_violations": guardrail or []}


# --- golden / 프롬프트 렌더 -------------------------------------------------
def test_load_golden_excludes_template():
    g = eval_loop.load_golden("eval/golden_set.yaml")
    ids = [c["id"] for c in g]
    assert "balayage_gangnam_damage" in ids
    assert all(not i.startswith("TEMPLATE") for i in ids)


def test_copygen_render_prompt_injects_fields():
    p = copygen.render_prompt(CASE)
    assert "손상 최소화 펌제" in p              # facts
    assert "재방문 시점을 카피에 각인" in p      # rag_principles
    assert "강남, 발레아주" in p                 # must_include join
    assert "연예인, 1위" in p                    # must_not_claim
    assert "발레아주" in p and "강남역" in p


def test_generate_copy_uses_provider(monkeypatch):
    captured = {}

    async def fake_complete(provider, prompt, models=None, timeout=60.0):
        captured.update(provider=provider, models=models)
        return "  생성된 카피  "

    monkeypatch.setattr(engines, "complete", fake_complete)
    for env in ("COPY_PROVIDER", "REPORT_PROVIDER", "COPY_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(env, raising=False)
    out = copygen.generate_copy(CASE)
    assert out == "생성된 카피"                         # strip
    assert captured["provider"] == "gemini"             # 기본
    assert captured["models"] == {"gemini": "gemini-2.5-flash"}


# --- judge 파싱 -------------------------------------------------------------
def test_parse_judge_handles_fences_and_prose():
    raw = '여기 결과:\n```json\n{"scores":{"A":5,"B":4,"C":5,"D":4,"E":5},"verdict":"pass"}\n```'
    v = eval_loop.parse_judge(raw)
    assert v["scores"]["A"] == 5 and v["verdict"] == "pass"


def test_parse_judge_raises_without_json():
    with pytest.raises(ValueError):
        eval_loop.parse_judge("JSON 없음")


def test_judge_calls_separate_provider(monkeypatch):
    captured = {}

    async def fake_complete(provider, prompt, models=None, timeout=60.0):
        captured["provider"] = provider
        captured["prompt"] = prompt
        return '{"scores":{"A":4,"B":4,"C":4,"D":4,"E":4},"guardrail_violations":[],"verdict":"pass"}'

    monkeypatch.setattr(engines, "complete", fake_complete)
    monkeypatch.setenv("JUDGE_PROVIDER", "openai")
    v = eval_loop.judge(CASE, "생성 카피 본문")
    assert captured["provider"] == "openai"            # 평가자 분리
    assert "생성 카피 본문" in captured["prompt"]      # 생성물이 프롬프트에 들어감
    assert v["scores"]["C"] == 4


# --- 순수 채점 로직 --------------------------------------------------------
def test_case_overall_and_pass():
    assert eval_loop.case_overall(_verdict(5, 5, 5, 5, 5)) == 5.0
    assert eval_loop.case_pass(_verdict(5, 4.5, 4.5, 5, 4.5)) is True
    assert eval_loop.case_pass(_verdict(5, 4, 5, 5, 5)) is False   # 한 축 미달


def test_guardrail_zeroes_overall():
    v = _verdict(5, 5, 5, 5, 5, guardrail=[{"rule": "환각", "quote": "연예인"}])
    assert eval_loop.case_overall(v) == 0.0
    assert eval_loop.case_pass(v) is False


def test_aggregate():
    results = [
        {"id": "a", "verdict": _verdict(5, 5, 4, 5, 5)},
        {"id": "b", "verdict": _verdict(4, 4, 4, 4, 4)},
    ]
    agg = eval_loop.aggregate(results)
    assert agg["axis_mean"]["A"] == 4.5 and agg["axis_mean"]["C"] == 4.0
    assert agg["weakest_axis"] == "C"          # C 평균 최저
    assert agg["total"] == 2 and agg["pass"] == 0   # b 는 전부 4 → 미달


def test_score_case_wires_generate_and_judge(monkeypatch):
    monkeypatch.setattr(copygen, "generate_copy", lambda case, **k: "카피")
    monkeypatch.setattr(eval_loop, "judge", lambda case, gen, **k: _verdict(5, 5, 5, 5, 5))
    r = eval_loop.score_case(CASE)
    assert r["id"] == "c1" and r["generated"] == "카피"
    assert eval_loop.case_pass(r["verdict"]) is True


def test_run_baseline(monkeypatch):
    monkeypatch.setattr(copygen, "generate_copy", lambda case, **k: "카피")
    monkeypatch.setattr(eval_loop, "judge", lambda case, gen, **k: _verdict(5, 5, 5, 5, 5))
    out = eval_loop.run_baseline(golden=[CASE])
    assert out["aggregate"]["pass"] == 1 and out["aggregate"]["overall"] == 5.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
