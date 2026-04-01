import time
from typing import AsyncIterator

from core.config import settings
from core.exceptions import ProviderError
from ai.providers.base import (
    BaseProvider, ChatRequest, ChatResponse,
    ProviderHealth, TokenChunk,
)

try:
    from groq import AsyncGroq
    _client = AsyncGroq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
except ImportError:
    _client = None


class GroqProvider(BaseProvider):
    """Groq: OpenAI-compatible API — fast, cheap, ideal for summarisation and simple tasks."""
    name = "groq"

    def _get_client(self):
        if not _client:
            raise ProviderError(self.name, "groq package not installed or API key missing")
        return _client

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        client = self._get_client()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            resp = await client.chat.completions.create(
                model=request.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=False,
            )
            choice = resp.choices[0]
            return ChatResponse(
                content=choice.message.content or "",
                model=resp.model,
                tokens_in=resp.usage.prompt_tokens,
                tokens_out=resp.usage.completion_tokens,
                finish_reason=choice.finish_reason or "stop",
            )
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def stream_completion(self, request: ChatRequest) -> AsyncIterator[TokenChunk]:
        client = self._get_client()
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            stream = await client.chat.completions.create(
                model=request.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield TokenChunk(text=delta.content, finish_reason=chunk.choices[0].finish_reason)
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def embed(self, texts: list[str], model: str = "nomic-embed-text-v1_5") -> list[list[float]]:
        # Groq does not yet offer a public embeddings endpoint — placeholder
        return [[0.0] * 1536 for _ in texts]

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            client = self._get_client()
            await client.models.list()
            return ProviderHealth(provider=self.name, healthy=True, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return ProviderHealth(provider=self.name, healthy=False, error=str(e))