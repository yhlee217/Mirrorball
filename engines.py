"""엔진 어댑터 — OpenAI / Gemini / Perplexity.

추상화 최소화: 엔진당 async 함수 하나 + 디스패처 하나.
각 query_* 함수는 성공 시 {"text", "citations", "model"} 를 반환하고,
실패는 예외로 올린다. 타임아웃/재시도/에러기록은 call_engine 이 담당한다.
"""

from __future__ import annotations

import asyncio
import os

# 엔진별 기본 모델 (순수 상수). .env 오버라이드는 resolve_models() 가 호출 시점에 읽는다.
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "perplexity": "sonar",
}


def resolve_models() -> dict[str, str]:
    """호출 시점에 환경변수(.env 로드 후)를 읽어 모델 맵을 만든다."""
    return {
        "openai": os.getenv("OPENAI_MODEL", DEFAULT_MODELS["openai"]),
        "gemini": os.getenv("GEMINI_MODEL", DEFAULT_MODELS["gemini"]),
        "perplexity": os.getenv("PERPLEXITY_MODEL", DEFAULT_MODELS["perplexity"]),
    }


# --- OpenAI (Responses API + web_search) ------------------------------------
async def query_openai(question: str, model: str, timeout: float) -> dict:
    from openai import AsyncOpenAI

    # 웹검색 도구 타입 (계정에 따라 web_search_preview 일 수 있어 .env 로 교체 가능)
    web_search_type = os.getenv("OPENAI_WEB_SEARCH_TYPE", "web_search")
    client = AsyncOpenAI()
    resp = await asyncio.wait_for(
        client.responses.create(
            model=model,
            input=question,
            tools=[{"type": web_search_type}],
            tool_choice="auto",
        ),
        timeout=timeout,
    )

    text = getattr(resp, "output_text", None) or ""
    citations: list[str] = []
    for item in getattr(resp, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            for ann in getattr(part, "annotations", None) or []:
                url = getattr(ann, "url", None)
                if url:
                    citations.append(url)

    return {"text": text, "citations": citations, "model": model}


# --- Gemini (google-genai + Google Search grounding) ------------------------
async def query_gemini(question: str, model: str, timeout: float) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client()  # GOOGLE_API_KEY 환경변수 사용
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
    resp = await asyncio.wait_for(
        client.aio.models.generate_content(
            model=model, contents=question, config=config
        ),
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
async def query_perplexity(question: str, model: str, timeout: float) -> dict:
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
    # Perplexity 는 비표준 최상위 citations 필드를 돌려준다 (OpenAI SDK 는 model_extra 에 보관)
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


async def call_engine(
    engine: str,
    question: str,
    models: dict[str, str] | None = None,
    timeout: float = 60.0,
    retries: int = 1,
) -> dict:
    """엔진 1회 질의. 타임아웃 60s, 실패 시 retries 회 재시도.

    끝까지 실패하면 예외를 올리지 않고 {"error": "..."} 를 반환한다
    (전체 실행은 계속되어야 하므로).
    """
    models = models or resolve_models()
    model = models.get(engine, DEFAULT_MODELS[engine])
    fn = ENGINES[engine]

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            result = await fn(question, model, timeout)
            result["error"] = None
            return result
        except Exception as exc:  # 네트워크/타임아웃/SDK 오류 모두 흡수
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(2 * (attempt + 1))

    return {
        "text": "",
        "citations": [],
        "model": model,
        "error": f"{type(last_err).__name__}: {last_err}",
    }
