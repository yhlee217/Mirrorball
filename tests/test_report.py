"""report 집계/렌더/생성 — fake Anthropic SDK 로 네트워크 없이 검증."""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import report  # noqa: E402

RAW = {
    "designer": {"name": "김민지", "aliases": ["민지 디자이너"]},
    "salon": {"name": "살롱드헤어 강남점", "aliases": ["살롱드헤어"]},
    "region": "강남역",
    "specialties": ["발레아주"],
    "sampling": 2,
    "run_at": "2026-06-09T21:10",
    "models": {"openai": "gpt-4o", "gemini": "gemini-2.5-flash", "perplexity": "sonar"},
    "records": [
        # 질문1: openai 2샘플 중 1회 언급, perplexity 미언급, gemini 실패
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


def test_aggregate_counts():
    agg = report._aggregate(RAW)
    assert agg["total_calls"] == 6
    assert agg["success"] == 4  # gemini 2건 실패
    assert agg["failed"] == 2
    assert agg["total_mentions"] == 1  # openai 1샘플만 언급


def test_aggregate_rows_structure():
    agg = report._aggregate(RAW)
    assert agg["questions"] == ["Q1"]
    row = agg["rows"][0]
    assert row["engines"]["openai"]["mentioned"] is True
    assert row["engines"]["openai"]["ratio"] == "1/2"
    assert row["engines"]["openai"]["context"] == "살롱드헤어 강남점 추천."
    assert row["engines"]["gemini"]["mentioned"] is False
    assert row["engines"]["gemini"]["ratio"] == "0/2"
    assert row["engines"]["perplexity"]["label"] == "Perplexity"


def test_aggregate_domains_and_competitors():
    agg = report._aggregate(RAW)
    domains = dict(agg["domains"])
    assert domains["blog.naver.com"] == 1
    assert domains["m.place.naver.com"] == 1
    assert domains["dcinside.com"] == 1  # www. 제거됨
    comps = dict(agg["competitors"])
    assert comps["미미헤어"] == 2
    assert comps["라온살롱"] == 1


def test_render_prompt_contains_key_fields():
    p = report.render_prompt(RAW)
    assert "김민지" in p
    assert "살롱드헤어" in p
    assert "blog.naver.com" in p
    assert "미미헤어" in p
    assert "측정일: 2026-06-09T21:10" in p
    assert "2회 반복" in p  # sampling 반영


def test_generate_report_uses_text_blocks_only(monkeypatch):
    """fake Anthropic 으로: thinking 블록은 빼고 text 블록만 이어붙이는지 + 모델 기본값."""
    captured = {}

    block = types.SimpleNamespace
    fake_message = types.SimpleNamespace(content=[
        block(type="thinking", thinking="속으로 생각...", text=None),
        block(type="text", text="# 한눈에 보기\n좋습니다.", thinking=None),
        block(type="text", text=" 추가 문단.", thinking=None),
    ])

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return fake_message

    class FakeMessages:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return FakeStream()

    class FakeAnthropic:
        def __init__(self, *a, **k):
            self.messages = FakeMessages()

    fake_module = types.SimpleNamespace(Anthropic=FakeAnthropic)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    md = report.generate_report(RAW)
    assert md == "# 한눈에 보기\n좋습니다. 추가 문단."  # thinking 제외, text 만
    assert captured["model"] == "claude-sonnet-4-6"  # 기본 모델
    assert captured["thinking"] == {"type": "adaptive"}


def test_generate_report_model_override(monkeypatch):
    captured = {}
    fake_message = types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text="ok")]
    )

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return fake_message

    class FakeAnthropic:
        def __init__(self, *a, **k):
            self.messages = types.SimpleNamespace(
                stream=lambda **kw: (captured.update(kw), FakeStream())[1]
            )

    monkeypatch.setitem(sys.modules, "anthropic",
                        types.SimpleNamespace(Anthropic=FakeAnthropic))
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    report.generate_report(RAW)
    assert captured["model"] == "claude-opus-4-8"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
