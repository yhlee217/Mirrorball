"""diagnose.run_all 오케스트레이션 + config 검증 — engines 를 fake 로 대체."""

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


def test_run_all_record_count(monkeypatch):
    async def fake_call(engine, question, models):
        text = "살롱드헤어 강남점 김민지 디자이너 추천" if engine == "openai" else "다른 곳 추천"
        return {"text": text, "citations": ["https://blog.naver.com/x"],
                "model": models[engine], "error": None}

    monkeypatch.setattr(engines, "call_engine", fake_call)
    records = asyncio.run(diagnose.run_all(CONFIG, MODELS))

    # 질문 2 × 엔진 3 × 샘플 2 = 12
    assert len(records) == 12
    # openai 레코드는 언급됨, 나머지는 아님
    openai_recs = [r for r in records if r["engine"] == "openai"]
    assert all(r["extraction"]["mentioned"] for r in openai_recs)
    other = [r for r in records if r["engine"] != "openai"]
    assert all(not r["extraction"]["mentioned"] for r in other)


def test_run_all_partial_failure_still_returns_all(monkeypatch):
    async def fake_call(engine, question, models):
        if engine == "gemini":
            return {"text": "", "citations": [], "model": models[engine],
                    "error": "TimeoutError: x"}
        return {"text": "살롱드헤어 추천", "citations": [], "model": models[engine],
                "error": None}

    monkeypatch.setattr(engines, "call_engine", fake_call)
    records = asyncio.run(diagnose.run_all(CONFIG, MODELS))

    assert len(records) == 12  # 실패 포함 전부 보존
    gemini = [r for r in records if r["engine"] == "gemini"]
    assert all(r["error"] and r["extraction"] is None for r in gemini)
    ok = [r for r in records if r["engine"] != "gemini"]
    assert all(r["error"] is None and r["extraction"] is not None for r in ok)


def test_run_all_extraction_crash_is_isolated(monkeypatch):
    async def fake_call(engine, question, models):
        return {"text": "텍스트", "citations": [], "model": models[engine], "error": None}

    def boom(*a, **k):
        raise RuntimeError("추출 폭발")

    monkeypatch.setattr(engines, "call_engine", fake_call)
    monkeypatch.setattr(extract, "analyze", boom)
    records = asyncio.run(diagnose.run_all(CONFIG, MODELS))

    # 추출이 모두 터져도 12개 레코드는 다 돌아오고, 각자 error 에 기록됨
    assert len(records) == 12
    assert all(r["error"] and "추출 폭발" in r["error"] for r in records)


def test_load_config_rejects_missing_questions(tmp_path):
    import pytest

    p = tmp_path / "bad.yaml"
    p.write_text("designer:\n  name: 김민지\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        diagnose.load_config(str(p))


def test_load_config_defaults(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text(
        "designer:\n  name: 김민지\nquestions:\n  - 질문1\n", encoding="utf-8"
    )
    cfg = diagnose.load_config(str(p))
    assert cfg["sampling"] == 1  # 기본값
    assert cfg["questions"] == ["질문1"]


def test_slug_from_path():
    assert diagnose.slug_from_path("targets/kimminji.yaml") == "kimminji"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
