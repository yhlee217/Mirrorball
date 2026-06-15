"""compare.py — 발행 전후 비교 (mock raw.json, 네트워크 없음)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import compare  # noqa: E402


def _raw(run_at, recs):
    return {"run_at": run_at, "records": recs}


def rec(q, eng, mentioned, error=None, citations=None, comps=None):
    return {
        "question": q, "engine": eng, "error": error,
        "extraction": None if error else {
            "mentioned": mentioned, "context": None,
            "citations": citations or [], "competitors_mentioned": comps or [],
        },
    }


BEFORE = _raw("2026-05-01T10:00", [
    rec("Q1", "openai", False, citations=["https://blog.naver.com/a"]),
    rec("Q1", "gemini", False),
    rec("Q2", "openai", False, comps=["미미헤어"]),
    rec("Q2", "gemini", False, comps=["미미헤어"]),
])
AFTER = _raw("2026-06-01T10:00", [
    rec("Q1", "openai", True, citations=["https://blog.naver.com/a", "https://instagram.com/x"]),
    rec("Q1", "gemini", True),
    rec("Q2", "openai", True),
    rec("Q2", "gemini", False, comps=["미미헤어"]),
])


def test_summarize_counts():
    s = compare.summarize(AFTER)
    assert s["total_mentions"] == 3
    assert s["per_engine"] == {"openai": 2, "gemini": 1}
    assert s["per_q"] == {"Q1": 2, "Q2": 1}
    assert s["failed"] == 0 and s["success"] == 4


def test_summarize_handles_errors():
    raw = _raw("x", [rec("Q1", "gemini", False, error="TimeoutError")])
    s = compare.summarize(raw)
    assert s["failed"] == 1 and s["success"] == 0 and s["total_mentions"] == 0


def test_render_compare_deltas():
    md = compare.render_compare(compare.summarize(BEFORE), compare.summarize(AFTER))
    assert "0회 → 3회" in md and "▲ +3" in md      # 전체 언급 증가
    assert "발행 전 측정: 2026-05-01T10:00" in md
    assert "발행 후 측정: 2026-06-01T10:00" in md
    # 인용 출처: instagram.com 새로 등장
    assert "instagram.com" in md
    # 경쟁(미미헤어) 2 → 1 로 감소
    assert "미미헤어" in md and "▼ -1" in md


def test_delta_formats():
    assert compare._delta(1, 3) == "▲ +2"
    assert compare._delta(3, 1) == "▼ -2"
    assert compare._delta(2, 2) == "– 0"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
