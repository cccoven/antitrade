from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    """Base interface for LLM providers. Implement complete() to add a new provider."""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Send prompt to LLM and return the response text."""
        ...

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Stream response token-by-token. Default: falls back to complete()."""
        prompt = "\n\n".join(
            f"{'[System]' if m['role'] == 'system' else '[User]' if m['role'] == 'user' else '[Assistant]'}: {m['content']}"
            for m in messages
        )
        result = await self.complete(prompt)
        chunk_size = 4
        for i in range(0, len(result), chunk_size):
            yield result[i:i + chunk_size]
