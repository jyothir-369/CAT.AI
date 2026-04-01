import time
from typing import AsyncIterator

from core.config import settings
from core.exceptions import ProviderError
from ai.providers.base import (
    BaseProvider, ChatRequest, ChatResponse,
    ProviderHealth, TokenChunk,
)

try:
    import google.generativeai as genai
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    _available = bool(settings.GEMINI_API_KEY)
except ImportError:
    _available = False


class GeminiProvider(BaseProvider):
    """Google Gemini — best for long-context tasks (1M token window on 1.5 Pro)."""
    name = "gemini"

    def _get_model(self, model_id: str):
        if not _available:
            raise ProviderError(self.name, "google-generativeai not installed or API key missing")
        import google.generativeai as genai
        return genai.GenerativeModel(model_id)

    def _to_gemini_messages(self, messages):
        """Convert to Gemini's parts format, extract system instruction."""
        system = None
        history = []
        last_user = None
        for m in messages:
            if m.role == "system":
                system = m.content
            elif m.role == "user":
                last_user = m.content
                history.append({"role": "user", "parts": [m.content]})
            elif m.role == "assistant":
                history.append({"role": "model", "parts": [m.content]})
        return system, history[:-1] if history else [], last_user or ""

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        try:
            model = self._get_model(request.model)
            system, history, last_user = self._to_gemini_messages(request.messages)
            chat = model.start_chat(history=history)
            resp = await chat.send_message_async(last_user)
            text = resp.text
            return ChatResponse(
                content=text,
                model=request.model,
                tokens_in=0,   # Gemini SDK v0.x doesn't always expose usage
                tokens_out=len(text) // 4,
                finish_reason="stop",
            )
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def stream_completion(self, request: ChatRequest) -> AsyncIterator[TokenChunk]:
        try:
            model = self._get_model(request.model)
            _, history, last_user = self._to_gemini_messages(request.messages)
            chat = model.start_chat(history=history)
            async for chunk in await chat.send_message_async(last_user, stream=True):
                if chunk.text:
                    yield TokenChunk(text=chunk.text)
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def embed(self, texts: list[str], model: str = "models/text-embedding-004") -> list[list[float]]:
        try:
            import google.generativeai as genai
            results = []
            for text in texts:
                result = genai.embed_content(model=model, content=text)
                results.append(result["embedding"])
            return results
        except Exception as e:
            raise ProviderError(self.name, str(e))

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            self._get_model("gemini-1.5-flash")
            return ProviderHealth(provider=self.name, healthy=True, latency_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return ProviderHealth(provider=self.name, healthy=False, error=str(e))