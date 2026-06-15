"""compete.py — 경쟁 노출 집계/렌더 (mock records, 네트워크 없음)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import compete  # noqa: E402


def rec(eng, mentioned, error=None, comps=None):
    return {
        "question": "강남역 발레아주 미용실", "engine": eng, "error": error,
        "extraction": None if error else {
            "mentioned": mentioned, "context": None, "citations": [],
            "competitors_mentioned": comps or [],
        },
    }


RECORDS = [
    rec("openai", False, comps=["미미헤어", "라온살롱"]),
    rec("gemini", False, comps=["미미헤어"]),
    rec("perplexity", False, comps=["미미헤어", "청담스타일헤어"]),
    rec("openai", False, error="TimeoutError"),
]


def test_aggregate_ranks_competitors():
    agg = compete.aggregate_competitors(RECORDS, designer_names=["김민지"])
    assert agg["success"] == 3 and agg["failed"] == 1
    assert agg["competitors"][0] == ("미미헤어", 3)   # 최다
    assert ("라온살롱", 1) in agg["competitors"]
    assert agg["target_mentions"] == 0 and agg["has_target"] is True


def test_aggregate_target_mentions():
    recs = [rec("openai", True), rec("gemini", True)]
    agg = compete.aggregate_competitors(recs, designer_names=["김민지"])
    assert agg["target_mentions"] == 2


def test_render_zero_exposure_sales_line():
    agg = compete.aggregate_competitors(RECORDS, designer_names=["김민지"])
    md = compete.render_compete(agg, {"region": "강남역", "specialties": ["발레아주"],
                                      "designer": {"name": "김민지"}})
    assert "미미헤어" in md and "| 1 | 미미헤어 | 3 |" in md
    assert "한 번도 노출되지 않았습니다 (0회)" in md  # 영업 멘트
    assert "미미헤어" in md  # 대신 나오는 경쟁


def test_render_no_competitors():
    agg = compete.aggregate_competitors([rec("openai", False)], designer_names=[])
    md = compete.render_compete(agg, {"region": "강남", "specialties": ["펌"]})
    assert "뚜렷한 경쟁 노출이 잡히지 않았습니다" in md
    assert "## 대상 노출" not in md  # designer 없으면 대상 섹션 없음


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
