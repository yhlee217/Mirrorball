"""engines.call_engine / resolve_models 테스트 — 실제 SDK·네트워크 없이 fake 로."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import engines  # noqa: E402


def test_resolve_models_defaults(monkeypatch):
    for k in ("OPENAI_MODEL", "GEMINI_MODEL", "PERPLEXITY_MODEL"):
        monkeypatch.delenv(k, raising=False)
    m = engines.resolve_models()
    assert m == {"openai": "gpt-4o", "gemini": "gemini-2.5-flash", "perplexity": "sonar"}


def test_resolve_models_env_override(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("PERPLEXITY_MODEL", "sonar-pro")
    m = engines.resolve_models()
    assert m["openai"] == "gpt-4.1-mini"
    assert m["perplexity"] == "sonar-pro"
    assert m["gemini"] == "gemini-2.5-flash"  # 미설정은 기본값


def test_call_engine_success(monkeypatch):
    async def fake(question, model, timeout):
        return {"text": f"답변:{question}", "citations": ["https://x"], "model": model}

    monkeypatch.setitem(engines.ENGINES, "openai", fake)
    res = asyncio.run(engines.call_engine("openai", "질문", {"openai": "m"}))
    assert res["error"] is None
    assert res["text"] == "답변:질문"
    assert res["model"] == "m"


def test_call_engine_retry_then_success(monkeypatch):
    calls = {"n": 0}

    async def flaky(question, model, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("일시 오류")
        return {"text": "ok", "citations": [], "model": model}

    monkeypatch.setitem(engines.ENGINES, "openai", flaky)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    res = asyncio.run(engines.call_engine("openai", "q", {"openai": "m"}, retries=1))
    assert res["error"] is None
    assert calls["n"] == 2  # 1실패 + 1성공


def test_call_engine_error_after_exhaustion(monkeypatch):
    calls = {"n": 0}

    async def always_fail(question, model, timeout):
        calls["n"] += 1
        raise ValueError("계속 실패")

    monkeypatch.setitem(engines.ENGINES, "openai", always_fail)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    res = asyncio.run(engines.call_engine("openai", "q", {"openai": "m"}, retries=1))
    assert res["error"] is not None
    assert "ValueError" in res["error"]
    assert res["text"] == ""  # 실패 시 빈 텍스트
    assert calls["n"] == 2  # 최초 + 재시도 1회


def test_call_engine_timeout_captured_as_error(monkeypatch):
    async def times_out(question, model, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setitem(engines.ENGINES, "openai", times_out)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    res = asyncio.run(engines.call_engine("openai", "q", {"openai": "m"}, retries=1))
    assert res["error"] is not None
    assert "TimeoutError" in res["error"]


async def _noop_sleep(_seconds):
    return None


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
