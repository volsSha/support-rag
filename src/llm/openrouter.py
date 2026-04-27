from collections.abc import AsyncGenerator

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_settings

SYSTEM_PROMPT = """You are a helpful support assistant. Answer questions using ONLY the provided context. If the context doesn't contain enough information to answer confidently, say so. Always cite your sources by including [Source: title](url) links."""


class OpenRouterClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.openrouter.default_model
        self._max_tokens = settings.openrouter.max_tokens
        self._temperature = settings.openrouter.temperature
        self.last_usage: dict | None = None

        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter.api_key.get_secret_value(),
            default_headers={
                "HTTP-Referer": settings.app_url,
                "X-OpenRouter-Title": settings.app_name,
            },
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def stream_completion(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        model = model or self._model
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                self.last_usage = chunk.usage.model_dump()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> str:
        model = model or self._model
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        if response.usage:
            self.last_usage = response.usage.model_dump()
        return response.choices[0].message.content or ""


_client: OpenRouterClient | None = None


def get_llm_client() -> OpenRouterClient | None:
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client
