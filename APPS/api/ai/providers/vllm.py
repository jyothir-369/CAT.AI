import time
from typing import AsyncIterator

import httpx

from core.exceptions import ProviderError
from ai.providers.base import (
    BaseProvider, ChatRequest, ChatResponse,
    ProviderHealth, TokenChunk,
)


VLLM_BASE_URL = "http://localhost:8001/v1"  # override via env in production


class VLLMProvider(BaseProvider):
    """
    Self-hosted vLLM — OpenAI-compatible REST API.
    Deploy on EKS GPU nodes (g4dn.xlarge) for cost-optimised inference.
    """
    name = "vllm"

    def __init__(self, base_url: str = VLLM_BASE_URL):
        self.base_url = base_url
        self._http = httpx.AsyncClient(base_url=base_url, timeout=60.0)

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            resp = await self._http.post("/chat/completions", json={
                "model": request.model,
                "messages": messages,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "stream": False,
            })
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return ChatResponse(
                content=choice["message"]["content"],
                model=data.get("model", request.model),
                tokens_in=usage.get("prompt_tokens", 0),
                tokens_out=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
            )
        except httpx.HTTPError as e:
            raise ProviderError(self.name, str(e))

    async def stream_completion(self, request: ChatRequest) -> AsyncIterator[TokenChunk]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        try:
            async with self._http.stream("POST", "/chat/completions", json={
                "model": request.model,
                "messages": messages,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "stream": True,
            }) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        data = json.loads(line[6:])
                        delta = data["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield TokenChunk(text=delta["content"])
        except httpx.HTTPError as e:
            raise ProviderError(self.name, str(e))

    async def embed(self, texts: list[str], model: str = "default") -> list[list[float]]:
        try:
            resp = await self._http.post("/embeddings", json={"input": texts, "model": model})
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]
        except httpx.HTTPError as e:
            raise ProviderError(self.name, str(e))

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            resp = await self._http.get("/models")
            resp.raise_for_status()
            return ProviderHealth(provider=self.name, healthy=True, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return ProviderHealth(provider=self.name, healthy=False, error=str(e))