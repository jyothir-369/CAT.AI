from dataclasses import dataclass, field
from typing import AsyncIterator

from ai.providers.base import ChatMessage, ChatRequest, ChatResponse, TokenChunk
from ai.router import route
from ai.token_counter import count_tokens, estimate_cost, tokens_remaining
from ai.circuit_breaker import get_breaker
from core.exceptions import ProviderError


# Token budget for each prompt section (in priority order)
BUDGET = {
    "system":   500,
    "memory":   200,
    "rag":      1500,
    "history":  2000,
    "tools":    500,
    "user":     500,
    "response": 1000,
}


@dataclass
class OrchestratorRequest:
    user_message: str
    conversation_history: list[ChatMessage] = field(default_factory=list)
    system_prompt: str | None = None
    memories: list[str] = field(default_factory=list)
    rag_chunks: list[str] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    requested_model: str | None = None
    workspace_default_model: str | None = None
    stream: bool = False
    cost_optimise: bool = False


@dataclass
class OrchestratorResponse:
    content: str
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class Orchestrator:
    """
    Assembles prompts, manages token budgets, selects models, and
    proxies requests to the appropriate provider with failover.
    """

    async def complete(self, req: OrchestratorRequest) -> OrchestratorResponse:
        messages = self._assemble_messages(req)
        provider, model = route(
            requested_model=req.requested_model,
            workspace_default=req.workspace_default_model,
            needs_tools=bool(req.tools),
            cost_optimise=req.cost_optimise,
        )
        chat_req = ChatRequest(
            messages=messages,
            model=model,
            max_tokens=BUDGET["response"],
            tools=req.tools,
            stream=False,
        )
        resp = await self._call_with_failover(provider.name, chat_req)
        cost = estimate_cost(model, resp.tokens_in, resp.tokens_out)
        return OrchestratorResponse(
            content=resp.content,
            model=model,
            provider=provider.name,
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            cost_usd=cost,
        )

    async def stream(self, req: OrchestratorRequest) -> AsyncIterator[TokenChunk]:
        messages = self._assemble_messages(req)
        provider, model = route(
            requested_model=req.requested_model,
            workspace_default=req.workspace_default_model,
            needs_tools=bool(req.tools),
            cost_optimise=req.cost_optimise,
        )
        chat_req = ChatRequest(messages=messages, model=model, max_tokens=BUDGET["response"], stream=True)
        breaker = get_breaker(provider.name)
        try:
            async for chunk in provider.stream_completion(chat_req):
                yield chunk
            breaker.record_success()
        except ProviderError:
            breaker.record_failure()
            raise

    def _assemble_messages(self, req: OrchestratorRequest) -> list[ChatMessage]:
        """
        Assembles prompt sections in priority order, respecting token budgets.
        Order: system → memory → RAG → history → user message
        """
        messages: list[ChatMessage] = []

        # 1. System prompt
        system_parts = []
        if req.system_prompt:
            system_parts.append(req.system_prompt)
        if req.memories:
            memory_block = "Relevant context about this user:\n" + "\n".join(f"- {m}" for m in req.memories)
            system_parts.append(memory_block)
        if req.rag_chunks:
            rag_block = "Retrieved knowledge:\n" + "\n\n".join(req.rag_chunks)
            system_parts.append(rag_block)
        if system_parts:
            messages.append(ChatMessage(role="system", content="\n\n".join(system_parts)))

        # 2. Conversation history (trim to budget)
        history = req.conversation_history[-20:]  # max last 20 turns before token check
        model = req.requested_model or req.workspace_default_model or "gpt-4o"
        history_tokens = count_tokens(history, model)
        if history_tokens > BUDGET["history"]:
            # Keep most recent messages that fit
            trimmed = []
            budget = BUDGET["history"]
            for msg in reversed(history):
                cost = len(msg.content) // 4
                if budget - cost < 0:
                    break
                trimmed.insert(0, msg)
                budget -= cost
            history = trimmed
        messages.extend(history)

        # 3. Current user message
        messages.append(ChatMessage(role="user", content=req.user_message))
        return messages

    async def _call_with_failover(self, primary_provider: str, req: ChatRequest) -> "ChatResponse":
        from ai.router import FAILOVER_ORDER, _providers
        providers_to_try = [primary_provider] + [p for p in FAILOVER_ORDER if p != primary_provider]
        last_error = None
        for provider_name in providers_to_try:
            breaker = get_breaker(provider_name)
            if not breaker.is_available():
                continue
            try:
                provider = _providers[provider_name]
                resp = await provider.chat_completion(req)
                breaker.record_success()
                return resp
            except ProviderError as e:
                breaker.record_failure()
                last_error = e
        from core.exceptions import AllProvidersFailedError
        raise AllProvidersFailedError()


# Module-level singleton
orchestrator = Orchestrator()