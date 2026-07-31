import logging
from typing import AsyncIterator

from providers import LLMProvider

logger = logging.getLogger(__name__)


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Anthropic takes `system` separately; the rest must alternate user/assistant."""
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    convo = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("user", "assistant")
    ]
    return "\n\n".join(system_parts), convo


class AnthropicProvider(LLMProvider):
    """Native Anthropic API provider with streaming."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def _client(self):
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=self.api_key)

    async def complete(self, prompt: str) -> str:
        resp = await self._client().messages.create(
            model=self.model, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        if not text:
            raise RuntimeError("Anthropic provider returned empty content")
        return text

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        system, convo = _split_system(messages)
        async with self._client().messages.stream(
            model=self.model, max_tokens=2000, system=system, messages=convo,
        ) as stream:
            async for text in stream.text_stream:
                yield text
