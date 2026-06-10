"""Provider 어댑터 — OpenAI / Gemini / Perplexity.

추상화 최소화: provider당 함수 하나 + 디스패처.
- query_*: 웹검색 켠 질의 (web_search 토글로 리포트 생성에도 재사용)
- call_engine: 타임아웃/재시도(429 백오프)/에러기록
- active_engines: 키가 있는 provider만 자동 활성화
- complete: 웹검색 끈 일반 생성 (리포트용)

모델·provider 는 코드에 하드코딩하지 않는다. .env 로 지정하고,
비우면 DEFAULT_MODELS 의 합리적 기본값을 쓴다.
"""

from __future__ import annotations

import asyncio
import os

PROVIDERS = ("openai", "gemini", "perplexity")

# provider -> 활성화 판단에 쓰는 API 키 환경변수
KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
}

# provider -> 모델 env 변수
MODEL_ENV = {
    "openai": "OPENAI_MODEL",
    "gemini": "GEMINI_MODEL",
    "perplexity": "PERPLEXITY_MODEL",
}

# .env 의 모델을 비웠을 때 쓰는 합리적 기본값 (Gemini 는 무료 티어 제공)
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "perplexity": "sonar",
}


def active_engines() -> list[str]:
    """API 키가 채워진 provider 만 PROVIDERS 순서로 반환 (자동 활성화)."""
    return [p for p in PROVIDERS if (os.getenv(KEY_ENV[p]) or "").strip()]


def resolve_models() -> dict[str, str]:
    """호출 시점(.env 로드 후)에 모델 맵을 만든다. 빈 값이면 기본값."""
    return {p: (os.getenv(MODEL_ENV[p]) or "").strip() or DEFAULT_MODELS[p] for p in PROVIDERS}


# --- OpenAI (Responses API, web_search 옵션) --------------------------------
async def query_openai(question: str, model: str, timeout: float, web_search: bool = True) -> dict:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    kwargs: dict = {"model": model, "input": question}
    if web_search:
        # 계정에 따라 web_search_preview 일 수 있어 .env 로 교체 가능
        kwargs["tools"] = [{"type": os.getenv("OPENAI_WEB_SEARCH_TYPE", "web_search")}]
        kwargs["tool_choice"] = "auto"

    resp = await asyncio.wait_for(client.responses.create(**kwargs), timeout=timeout)

    text = getattr(resp, "output_text", None) or ""
    citations: list[str] = []
    for item in getattr(resp, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            for ann in getattr(part, "annotations", None) or []:
                url = getattr(ann, "url", None)
                if url:
                    citations.append(url)

    return {"text": text, "citations": citations, "model": model}


# --- Gemini (google-genai, Google Search grounding) -------------------------
async def query_gemini(question: str, model: str, timeout: float, web_search: bool = True) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client()  # GOOGLE_API_KEY 사용
    config = None
    if web_search:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

    resp = await asyncio.wait_for(
        client.aio.models.generate_content(model=model, contents=question, config=config),
        timeout=timeout,
    )

    text = getattr(resp, "text", None) or ""
    citations: list[str] = []
    for cand in getattr(resp, "candidates", None) or []:
        gm = getattr(cand, "grounding_metadata", None)
        for chunk in getattr(gm, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            uri = getattr(web, "uri", None)
            if uri:
                citations.append(uri)

    return {"text": text, "citations": citations, "model": model}


# --- Perplexity (OpenAI 호환 REST, sonar 계열) ------------------------------
async def query_perplexity(question: str, model: str, timeout: float, web_search: bool = True) -> dict:
    # sonar 는 항상 검색하므로 web_search 토글은 무시한다.
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.environ["PERPLEXITY_API_KEY"],
        base_url="https://api.perplexity.ai",
    )
    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
        ),
        timeout=timeout,
    )

    text = resp.choices[0].message.content or ""
    citations = (
        getattr(resp, "citations", None)
        or (getattr(resp, "model_extra", None) or {}).get("citations")
        or []
    )
    return {"text": text, "citations": list(citations), "model": model}


ENGINES = {
    "openai": query_openai,
    "gemini": query_gemini,
    "perplexity": query_perplexity,
}


def _is_rate_limit(exc: Exception) -> bool:
    s = f"{type(exc).__name__} {exc}".lower()
    return (
        "429" in s
        or "resource_exhausted" in s
        or "ratelimit" in s
        or ("rate" in s and "limit" in s)
    )


def _backoff_delay(exc: Exception, attempt: int) -> float:
    base = 15.0 if _is_rate_limit(exc) else 2.0  # 429 는 더 길게
    return base * (attempt + 1)


async def call_engine(
    engine: str,
    question: str,
    models: dict[str, str] | None = None,
    timeout: float = 60.0,
    retries: int = 1,
    web_search: bool = True,
) -> dict:
    """1회 질의. 타임아웃 60s, 실패 시 retries 회 재시도(429 백오프).

    끝까지 실패하면 예외를 올리지 않고 {"error": "..."} 를 반환한다.
    """
    models = models or resolve_models()
    model = models.get(engine) or DEFAULT_MODELS[engine]
    fn = ENGINES[engine]

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = await fn(question, model, timeout, web_search)
            result["error"] = None
            return result
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(_backoff_delay(exc, attempt))

    return {
        "text": "",
        "citations": [],
        "model": model,
        "error": f"{type(last_err).__name__}: {last_err}",
    }


async def complete(
    provider: str,
    prompt: str,
    models: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> str:
    """리포트용 일반 생성 (웹검색 OFF). query 함수를 재사용한다."""
    if provider not in PROVIDERS:
        raise ValueError(f"지원하지 않는 provider: {provider}")
    res = await call_engine(provider, prompt, models, timeout=timeout, web_search=False)
    if res.get("error"):
        raise RuntimeError(res["error"])
    return res["text"]
