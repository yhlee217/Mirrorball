"""diagnose 오케스트레이션 — engines 를 fake 로 대체. 활성 엔진 동적."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import diagnose  # noqa: E402
import engines  # noqa: E402
import extract  # noqa: E402

CONFIG = {
    "designer": {"name": "김민지", "aliases": ["민지 디자이너"]},
    "salon": {"name": "살롱드헤어 강남점", "aliases": ["살롱드헤어"]},
    "region": "강남역",
    "specialties": ["발레아주"],
    "sampling": 2,
    "questions": ["강남역 발레아주 미용실", "강남 디지털펌 디자이너"],
}
MODELS = {"openai": "m1", "gemini": "m2", "perplexity": "m3"}


def test_run_all_count_three_engines(monkeypatch):
    async def fake_call(engine, question, models):
        text = "살롱드헤어 강남점 김민지 디자이너 추천" if engine == "openai" else "다른 곳"
        return {"text": text, "citations": ["https://blog.naver.com/x"],
                "model": models[engine], "error": None}

    monkeypatch.setattr(engines, "call_engine", fake_call)
    recs = asyncio.run(diagnose.run_all(CONFIG, MODELS, ["openai", "gemini", "perplexity"]))
    assert len(recs) == 2 * 3 * 2  # 질문×엔진×샘플 = 12
    assert all(r["extraction"]["mentioned"] for r in recs if r["engine"] == "openai")


def test_run_all_single_engine(monkeypatch):
    async def fake_call(engine, question, models):
        return {"text": "살롱드헤어 추천", "citations": [], "model": models[engine], "error": None}

    monkeypatch.setattr(engines, "call_engine", fake_call)
    recs = asyncio.run(diagnose.run_all(CONFIG, MODELS, ["gemini"]))
    assert len(recs) == 2 * 1 * 2  # 엔진 1개 = 4
    assert {r["engine"] for r in recs} == {"gemini"}


def test_run_all_partial_failure_preserved(monkeypatch):
    async def fake_call(engine, question, models):
        if engine == "gemini":
            return {"text": "", "citations": [], "model": models[engine], "error": "TimeoutError: x"}
        return {"text": "살롱드헤어 추천", "citations": [], "model": models[engine], "error": None}

    monkeypatch.setattr(engines, "call_engine", fake_call)
    recs = asyncio.run(diagnose.run_all(CONFIG, MODELS, ["openai", "gemini"]))
    assert len(recs) == 8
    gem = [r for r in recs if r["engine"] == "gemini"]
    assert all(r["error"] and r["extraction"] is None for r in gem)


def test_run_all_extraction_crash_isolated(monkeypatch):
    async def fake_call(engine, question, models):
        return {"text": "텍스트", "citations": [], "model": models[engine], "error": None}

    monkeypatch.setattr(engines, "call_engine", fake_call)
    monkeypatch.setattr(extract, "analyze", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("폭발")))
    recs = asyncio.run(diagnose.run_all(CONFIG, MODELS, ["openai"]))
    assert len(recs) == 4
    assert all(r["error"] and "폭발" in r["error"] for r in recs)


# --- report provider 검증 ---------------------------------------------------
def test_resolve_report_provider_default(monkeypatch):
    monkeypatch.delenv("REPORT_PROVIDER", raising=False)
    assert diagnose.resolve_report_provider(["gemini"]) == "gemini"


def test_resolve_report_provider_unknown(monkeypatch):
    import pytest

    monkeypatch.setenv("REPORT_PROVIDER", "anthropic")
    with pytest.raises(SystemExit):
        diagnose.resolve_report_provider(["gemini"])


def test_resolve_report_provider_inactive(monkeypatch):
    import pytest

    monkeypatch.setenv("REPORT_PROVIDER", "openai")  # 활성 목록에 없음
    with pytest.raises(SystemExit):
        diagnose.resolve_report_provider(["gemini"])


# --- config / 기타 ----------------------------------------------------------
def test_load_config_rejects_missing_questions(tmp_path):
    import pytest

    p = tmp_path / "bad.yaml"
    p.write_text("designer:\n  name: 김민지\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        diagnose.load_config(str(p))


def test_load_config_defaults(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text("designer:\n  name: 김민지\nquestions:\n  - 질문1\n", encoding="utf-8")
    cfg = diagnose.load_config(str(p))
    assert cfg["sampling"] == 1 and cfg["questions"] == ["질문1"]


def test_confirm_cost_total(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "y")
    assert diagnose.confirm_cost(4, 2, 3) is True
    assert "총 24회" in capsys.readouterr().out  # 4×2×3


def test_slug_from_path():
    assert diagnose.slug_from_path("targets/kimminji.yaml") == "kimminji"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
