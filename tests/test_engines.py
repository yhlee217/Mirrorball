"""engines — 자동 활성화 / call_engine / 백오프 / complete. 실제 SDK 없이 fake."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import engines  # noqa: E402


async def _noop_sleep(_seconds):
    return None


# --- active_engines ---------------------------------------------------------
def test_active_engines_detects_keys(monkeypatch):
    for env in engines.KEY_ENV.values():
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    assert engines.active_engines() == ["gemini"]


def test_active_engines_empty_string_inactive(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")  # 빈 값은 비활성
    monkeypatch.setenv("GOOGLE_API_KEY", "  ")  # 공백도 비활성
    monkeypatch.setenv("PERPLEXITY_API_KEY", "p-key")
    assert engines.active_engines() == ["perplexity"]


def test_active_engines_order_and_multi(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    assert engines.active_engines() == ["openai", "gemini"]  # PROVIDERS 순서


# --- resolve_models ---------------------------------------------------------
def test_resolve_models_defaults(monkeypatch):
    for env in engines.MODEL_ENV.values():
        monkeypatch.delenv(env, raising=False)
    m = engines.resolve_models()
    assert m == {"openai": "gpt-4o", "gemini": "gemini-2.5-flash", "perplexity": "sonar"}


def test_resolve_models_empty_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "")  # 빈 값 → 기본값
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    m = engines.resolve_models()
    assert m["gemini"] == "gemini-2.5-flash"
    assert m["openai"] == "gpt-4.1-mini"


# --- call_engine ------------------------------------------------------------
def test_call_engine_success(monkeypatch):
    async def fake(question, model, timeout, web_search=True):
        return {"text": f"답변:{question}", "citations": ["https://x"], "model": model}

    monkeypatch.setitem(engines.ENGINES, "openai", fake)
    res = asyncio.run(engines.call_engine("openai", "질문", {"openai": "m"}))
    assert res["error"] is None and res["text"] == "답변:질문" and res["model"] == "m"


def test_call_engine_passes_web_search_flag(monkeypatch):
    seen = {}

    async def fake(question, model, timeout, web_search=True):
        seen["web_search"] = web_search
        return {"text": "", "citations": [], "model": model}

    monkeypatch.setitem(engines.ENGINES, "gemini", fake)
    asyncio.run(engines.call_engine("gemini", "q", {"gemini": "m"}, web_search=False))
    assert seen["web_search"] is False


def test_call_engine_retry_then_success(monkeypatch):
    calls = {"n": 0}

    async def flaky(question, model, timeout, web_search=True):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("일시 오류")
        return {"text": "ok", "citations": [], "model": model}

    monkeypatch.setitem(engines.ENGINES, "openai", flaky)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    res = asyncio.run(engines.call_engine("openai", "q", {"openai": "m"}, retries=1))
    assert res["error"] is None and calls["n"] == 2


def test_call_engine_error_after_exhaustion(monkeypatch):
    calls = {"n": 0}

    async def always_fail(question, model, timeout, web_search=True):
        calls["n"] += 1
        raise ValueError("계속 실패")

    monkeypatch.setitem(engines.ENGINES, "openai", always_fail)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    res = asyncio.run(engines.call_engine("openai", "q", {"openai": "m"}, retries=1))
    assert res["error"] and "ValueError" in res["error"]
    assert res["text"] == "" and calls["n"] == 2


def test_call_engine_timeout_captured(monkeypatch):
    async def times_out(question, model, timeout, web_search=True):
        raise asyncio.TimeoutError()

    monkeypatch.setitem(engines.ENGINES, "openai", times_out)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    res = asyncio.run(engines.call_engine("openai", "q", {"openai": "m"}, retries=1))
    assert res["error"] and "TimeoutError" in res["error"]


# --- 429 백오프 --------------------------------------------------------------
def test_rate_limit_detection():
    assert engines._is_rate_limit(Exception("Error 429 Too Many Requests"))
    assert engines._is_rate_limit(Exception("RESOURCE_EXHAUSTED"))
    assert engines._is_rate_limit(Exception("rate limit exceeded"))
    assert not engines._is_rate_limit(Exception("connection refused"))


def test_backoff_longer_for_rate_limit():
    rl = engines._backoff_delay(Exception("429"), 0)
    normal = engines._backoff_delay(Exception("boom"), 0)
    assert rl > normal  # 429 는 더 길게


def test_call_engine_429_uses_backoff(monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    async def rate_limited(question, model, timeout, web_search=True):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setitem(engines.ENGINES, "gemini", rate_limited)
    monkeypatch.setattr(engines.asyncio, "sleep", fake_sleep)
    res = asyncio.run(engines.call_engine("gemini", "q", {"gemini": "m"}, retries=1))
    assert res["error"] and slept and slept[0] >= 15.0  # 백오프 적용


# --- complete (리포트용, web_search OFF) ------------------------------------
def test_complete_returns_text(monkeypatch):
    seen = {}

    async def fake(question, model, timeout, web_search=True):
        seen["web_search"] = web_search
        return {"text": "리포트 본문", "citations": [], "model": model}

    monkeypatch.setitem(engines.ENGINES, "gemini", fake)
    out = asyncio.run(engines.complete("gemini", "프롬프트", {"gemini": "m"}))
    assert out == "리포트 본문"
    assert seen["web_search"] is False  # 리포트는 검색 안 함


def test_complete_raises_on_error(monkeypatch):
    import pytest

    async def fail(question, model, timeout, web_search=True):
        raise RuntimeError("죽음")

    monkeypatch.setitem(engines.ENGINES, "gemini", fail)
    monkeypatch.setattr(engines.asyncio, "sleep", _noop_sleep)
    with pytest.raises(RuntimeError):
        asyncio.run(engines.complete("gemini", "p", {"gemini": "m"}))


def test_complete_rejects_unknown_provider():
    import pytest

    with pytest.raises(ValueError):
        asyncio.run(engines.complete("anthropic", "p", {}))


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
