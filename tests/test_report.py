"""report 집계/렌더/생성 — engines.complete 를 fake 로 (네트워크 없음)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import engines  # noqa: E402
import report  # noqa: E402

RAW = {
    "designer": {"name": "김민지", "aliases": ["민지 디자이너"]},
    "salon": {"name": "살롱드헤어 강남점", "aliases": ["살롱드헤어"]},
    "region": "강남역",
    "specialties": ["발레아주"],
    "sampling": 2,
    "run_at": "2026-06-09T21:10",
    "models": {"openai": "gpt-4o", "gemini": "gemini-2.5-flash", "perplexity": "sonar"},
    "report_provider": "gemini",
    "records": [
        {"question": "Q1", "engine": "openai", "sample_idx": 0, "error": None,
         "extraction": {"mentioned": True, "context": "살롱드헤어 강남점 추천.",
                        "citations": ["https://blog.naver.com/a"],
                        "competitors_mentioned": ["미미헤어"]}},
        {"question": "Q1", "engine": "openai", "sample_idx": 1, "error": None,
         "extraction": {"mentioned": False, "context": None,
                        "citations": ["https://m.place.naver.com/b"],
                        "competitors_mentioned": ["미미헤어", "라온살롱"]}},
        {"question": "Q1", "engine": "gemini", "sample_idx": 0,
         "error": "TimeoutError: x", "extraction": None},
        {"question": "Q1", "engine": "gemini", "sample_idx": 1,
         "error": "TimeoutError: x", "extraction": None},
        {"question": "Q1", "engine": "perplexity", "sample_idx": 0, "error": None,
         "extraction": {"mentioned": False, "context": None,
                        "citations": ["https://www.dcinside.com/c"],
                        "competitors_mentioned": []}},
        {"question": "Q1", "engine": "perplexity", "sample_idx": 1, "error": None,
         "extraction": {"mentioned": False, "context": None, "citations": [],
                        "competitors_mentioned": []}},
    ],
}

# 단일 엔진(gemini) 만 활성이었던 실행
RAW_SINGLE = {
    **RAW,
    "records": [
        {"question": "Q1", "engine": "gemini", "sample_idx": 0, "error": None,
         "extraction": {"mentioned": True, "context": "살롱드헤어 추천.",
                        "citations": ["https://blog.naver.com/z"], "competitors_mentioned": []}},
    ],
}


def test_aggregate_counts():
    agg = report._aggregate(RAW)
    assert agg["total_calls"] == 6
    assert agg["success"] == 4 and agg["failed"] == 2
    assert agg["total_mentions"] == 1


def test_aggregate_engines_used_dynamic():
    assert report._aggregate(RAW)["engines_used"] == ["openai", "gemini", "perplexity"]
    agg1 = report._aggregate(RAW_SINGLE)
    assert agg1["engines_used"] == ["gemini"]
    assert list(agg1["rows"][0]["engines"].keys()) == ["gemini"]  # 컬럼도 1개


def test_aggregate_rows_structure():
    agg = report._aggregate(RAW)
    row = agg["rows"][0]
    assert row["engines"]["openai"]["mentioned"] is True
    assert row["engines"]["openai"]["ratio"] == "1/2"
    assert row["engines"]["openai"]["context"] == "살롱드헤어 강남점 추천."
    assert row["engines"]["gemini"]["mentioned"] is False
    assert row["engines"]["perplexity"]["label"] == "Perplexity"


def test_aggregate_domains_and_competitors():
    agg = report._aggregate(RAW)
    domains = dict(agg["domains"])
    assert domains["blog.naver.com"] == 1
    assert domains["m.place.naver.com"] == 1
    assert domains["dcinside.com"] == 1  # www. 제거
    comps = dict(agg["competitors"])
    assert comps["미미헤어"] == 2 and comps["라온살롱"] == 1


def test_render_prompt_contains_key_fields():
    p = report.render_prompt(RAW)
    assert "김민지" in p and "살롱드헤어" in p
    assert "blog.naver.com" in p and "미미헤어" in p
    assert "측정일: 2026-06-09T21:10" in p
    assert "2회 반복" in p


def test_render_prompt_single_engine_columns():
    p = report.render_prompt(RAW_SINGLE)
    assert "GEMINI" in p  # 측정에 사용한 AI 목록
    assert "ChatGPT" not in p  # 비활성 엔진은 표/요약에 없음


def test_generate_report_default_provider(monkeypatch):
    captured = {}

    async def fake_complete(provider, prompt, models=None, timeout=60.0):
        captured.update(provider=provider, prompt=prompt, models=models)
        return "  # 진단 리포트\n본문  "

    monkeypatch.setattr(engines, "complete", fake_complete)
    for env in ("REPORT_PROVIDER", "REPORT_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(env, raising=False)

    md = report.generate_report(RAW)
    assert md == "# 진단 리포트\n본문"  # strip 적용
    assert captured["provider"] == "gemini"  # 기본 provider
    assert captured["models"] == {"gemini": "gemini-2.5-flash"}  # 기본 모델
    assert "김민지" in captured["prompt"]


def test_generate_report_provider_and_model_override(monkeypatch):
    captured = {}

    async def fake_complete(provider, prompt, models=None, timeout=60.0):
        captured.update(provider=provider, models=models)
        return "ok"

    monkeypatch.setattr(engines, "complete", fake_complete)
    monkeypatch.setenv("REPORT_PROVIDER", "openai")
    monkeypatch.setenv("REPORT_MODEL", "gpt-4.1")
    report.generate_report(RAW)
    assert captured["provider"] == "openai"
    assert captured["models"] == {"openai": "gpt-4.1"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
