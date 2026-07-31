import logging
from typing import AsyncIterator

from providers import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible API provider (works with proxies/relays via custom base_url)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def _client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

    async def complete(self, prompt: str) -> str:
        response = await self._client().chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        content = response.choices[0].message.content or ""
        if not content:
            raise RuntimeError("OpenAI provider returned empty content")
        return content

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = await self._client().chat.completions.create(
            model=self.model, messages=messages, temperature=0.3,
            max_tokens=2000, stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
