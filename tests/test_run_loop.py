"""run_loop.py — 자율 루프 제어 로직. LLM 없이 evaluate/propose 주입으로 검증."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import run_loop  # noqa: E402


def agg(overall, axes, p, total=2):
    return {"overall": overall, "axis_mean": dict(zip("ABCDE", axes)),
            "pass": p, "total": total, "weakest_axis": "C"}


# --- 순수 제어 로직 --------------------------------------------------------
def test_passed():
    assert run_loop.passed(agg(5, [5, 5, 5, 5, 5], 2, 2)) is True
    assert run_loop.passed(agg(4, [4, 4, 4, 4, 4], 1, 2)) is False


def test_better_accepts_improvement():
    old = agg(3.0, [3, 3, 3, 3, 3], 0)
    new = agg(3.5, [3, 3, 4, 3, 4], 0)   # 총점↑, 회귀 없음
    assert run_loop.better(new, old) is True


def test_better_rejects_regression():
    old = agg(3.0, [3, 3, 3, 3, 3], 0)
    new = agg(3.2, [3, 2, 4, 4, 3], 0)   # 총점은↑지만 B축 3→2 회귀
    assert run_loop.better(new, old) is False


def test_better_rejects_no_overall_gain():
    old = agg(3.0, [3, 3, 3, 3, 3], 0)
    assert run_loop.better(agg(3.0, [3, 3, 3, 3, 3], 0), old) is False


# --- 루프 (mock evaluate/propose) ------------------------------------------
def _stub_prompt(tmp_path):
    p = tmp_path / "copy.md.j2"
    p.write_text("v0", encoding="utf-8")
    return str(p)


def test_run_improves_then_stops_all_pass(tmp_path):
    # 버전이 오를수록 점수 상승, v3 에서 전부 pass
    table = {
        "v0": agg(3.0, [3, 3, 3, 3, 3], 0),
        "v1": agg(4.0, [4, 4, 4, 4, 4], 0),
        "v2": agg(4.6, [4.6] * 5, 2, 2),
    }
    seq = ["v1", "v2"]
    calls = {"n": 0}

    def evaluate(text):
        return table[text], []

    def propose(cur, a, r):
        v = seq[calls["n"]]
        calls["n"] += 1
        return v

    out = run_loop.run(_stub_prompt(tmp_path), golden=[{}],
                       evaluate=evaluate, propose=propose, max_iters=5)
    actions = [e["action"] for e in out["log"]]
    assert actions[0] == "baseline"
    assert "accept" in actions and actions[-1] == "stop_all_pass"
    assert out["aggregate"]["pass"] == 2          # 최종 전부 pass
    assert out["final_prompt"] == "v2"            # 채택된 최선 버전


def test_run_rollback_then_plateau(tmp_path):
    # 제안이 매번 더 나쁨 → 전부 롤백 → patience 후 플래토 정지
    base = agg(4.0, [4, 4, 4, 4, 4], 0)
    worse = agg(3.0, [3, 3, 3, 3, 3], 0)

    def evaluate(text):
        return (base if text == "v0" else worse), []

    def propose(cur, a, r):
        return "worse"

    out = run_loop.run(_stub_prompt(tmp_path), golden=[{}],
                       evaluate=evaluate, propose=propose, max_iters=10, patience=3)
    actions = [e["action"] for e in out["log"]]
    assert actions.count("rollback") == 3 and actions[-1] == "stop_plateau"
    assert out["final_prompt"] == "v0"            # 베이스라인 유지(롤백)


def test_run_respects_max_iters(tmp_path):
    # 계속 조금씩 좋아지지만 pass 도 플래토도 아님 → max_iters 에서 종료
    scores = {"v0": agg(2.0, [2] * 5, 0)}

    def evaluate(text):
        if text not in scores:
            prev = max(s["overall"] for s in scores.values())
            scores[text] = agg(prev + 0.1, [prev + 0.1] * 5, 0)
        return scores[text], []

    def propose(cur, a, r):
        return f"v{len(scores)}"

    out = run_loop.run(_stub_prompt(tmp_path), golden=[{}],
                       evaluate=evaluate, propose=propose, max_iters=4, patience=99)
    iters = [e["iter"] for e in out["log"]]
    assert max(iters) == 4                         # max_iters 까지만


def test_collect_failures_limit():
    results = [{"verdict": {"failures": [{"axis": "C", "quote": "q", "why": "w"}] * 5}}]
    assert len(run_loop.collect_failures(results, limit=3)) == 3


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
