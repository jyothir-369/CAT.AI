import time
from typing import AsyncIterator

from core.config import settings
from core.exceptions import ProviderError
from ai.providers.base import (
    BaseProvider, ChatRequest, ChatResponse,
    ProviderHealth, TokenChunk,
)

try:
    from openai import AsyncOpenAI
    _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
except ImportError:
    _client = None


class OpenAIProvider(BaseProvider):
    name = "openai"

    def _get_client(self) -> "AsyncOpenAI":
        if not _client:
            raise ProviderError(self.name, "openai package not installed or API key missing")
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
                tools=request.tools or None,
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
                finish = chunk.choices[0].finish_reason
                if delta.content:
                    yield TokenChunk(text=delta.content, finish_reason=finish)
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def embed(self, texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
        client = self._get_client()
        try:
            resp = await client.embeddings.create(input=texts, model=model)
            return [item.embedding for item in resp.data]
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            client = self._get_client()
            await client.models.list()
            return ProviderHealth(provider=self.name, healthy=True, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return ProviderHealth(provider=self.name, healthy=False, error=str(e))

    def token_count(self, messages, model: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(model)
            return sum(len(enc.encode(m.content)) + 4 for m in messages)
        except Exception:
            return super().token_count(messages, model)