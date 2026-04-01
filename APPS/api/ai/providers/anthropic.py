import time
from typing import AsyncIterator

from core.config import settings
from core.exceptions import ProviderError
from ai.providers.base import (
    BaseProvider, ChatRequest, ChatResponse,
    ProviderHealth, TokenChunk,
)

try:
    import anthropic as _anthropic_sdk
    _client = _anthropic_sdk.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
except ImportError:
    _client = None


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def _get_client(self):
        if not _client:
            raise ProviderError(self.name, "anthropic package not installed or API key missing")
        return _client

    def _split_messages(self, messages):
        """Anthropic separates the system prompt from the messages array."""
        system = None
        filtered = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                filtered.append({"role": m.role, "content": m.content})
        return system, filtered

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        client = self._get_client()
        system, messages = self._split_messages(request.messages)
        try:
            kwargs = dict(
                model=request.model,
                max_tokens=request.max_tokens,
                messages=messages,
            )
            if system:
                kwargs["system"] = system
            if request.tools:
                kwargs["tools"] = request.tools

            resp = await client.messages.create(**kwargs)
            content = "".join(b.text for b in resp.content if hasattr(b, "text"))
            return ChatResponse(
                content=content,
                model=resp.model,
                tokens_in=resp.usage.input_tokens,
                tokens_out=resp.usage.output_tokens,
                finish_reason=resp.stop_reason or "stop",
            )
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def stream_completion(self, request: ChatRequest) -> AsyncIterator[TokenChunk]:
        client = self._get_client()
        system, messages = self._split_messages(request.messages)
        try:
            kwargs = dict(
                model=request.model,
                max_tokens=request.max_tokens,
                messages=messages,
                stream=True,
            )
            if system:
                kwargs["system"] = system

            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield TokenChunk(text=text)
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def embed(self, texts: list[str], model: str = "voyage-2") -> list[list[float]]:
        # Anthropic embedding via Voyage — placeholder returns zeros
        return [[0.0] * 1536 for _ in texts]

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            client = self._get_client()
            await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return ProviderHealth(provider=self.name, healthy=True, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return ProviderHealth(provider=self.name, healthy=False, error=str(e))