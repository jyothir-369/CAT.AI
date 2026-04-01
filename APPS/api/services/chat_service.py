from typing import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ai.orchestrator import Orchestrator, OrchestratorRequest, orchestrator
from ai.providers.base import ChatMessage, TokenChunk
from ai.guardrails import moderate_input, log_flag
from ai.token_counter import estimate_cost
from db.repos.conversation_repo import ConversationRepo
from db.repos.memory_repo import MemoryRepo
from core.exceptions import NotFoundError


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepo(db)
        self.mem_repo = MemoryRepo(db)
        self._orchestrator = orchestrator

    async def chat(
        self,
        org_id: str,
        user_id: str,
        conversation_id: str,
        message: str,
        model: str | None = None,
    ) -> dict:
        """Non-streaming chat completion."""
        conv = await self.conv_repo.get_by_id(UUID(conversation_id), UUID(org_id))
        if not conv:
            raise NotFoundError("Conversation", conversation_id)

        # Moderate input
        flag = await moderate_input(message, org_id=org_id)
        log_flag(flag, {"org_id": org_id, "user_id": user_id})

        # Load history
        history_msgs = await self.conv_repo.get_messages(UUID(conversation_id))
        history = [ChatMessage(role=m.role, content=m.content) for m in history_msgs]

        # Load top-k memories
        memories = await self.mem_repo.list_by_user(UUID(user_id), UUID(org_id), limit=5)
        memory_texts = [m.content for m in memories]

        req = OrchestratorRequest(
            user_message=message,
            conversation_history=history,
            system_prompt=conv.system_prompt,
            memories=memory_texts,
            requested_model=model or conv.model_id,
        )
        result = await self._orchestrator.complete(req)

        # Persist both turns
        await self.conv_repo.add_message(
            UUID(conversation_id), role="user", content=message
        )
        await self.conv_repo.add_message(
            UUID(conversation_id),
            role="assistant",
            content=result.content,
            model_id=result.model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
        )

        return {
            "response": result.content,
            "model": result.model,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_usd": result.cost_usd,
        }

    async def stream(
        self,
        org_id: str,
        user_id: str,
        conversation_id: str,
        message: str,
        model: str | None = None,
    ) -> AsyncIterator[TokenChunk]:
        """SSE streaming completion. Caller sends chunks as SSE events."""
        conv = await self.conv_repo.get_by_id(UUID(conversation_id), UUID(org_id))
        if not conv:
            raise NotFoundError("Conversation", conversation_id)

        history_msgs = await self.conv_repo.get_messages(UUID(conversation_id))
        history = [ChatMessage(role=m.role, content=m.content) for m in history_msgs]

        memories = await self.mem_repo.list_by_user(UUID(user_id), UUID(org_id), limit=5)
        memory_texts = [m.content for m in memories]

        # Persist user message before streaming starts
        await self.conv_repo.add_message(UUID(conversation_id), role="user", content=message)

        req = OrchestratorRequest(
            user_message=message,
            conversation_history=history,
            system_prompt=conv.system_prompt,
            memories=memory_texts,
            requested_model=model or conv.model_id,
            stream=True,
        )

        full_response = []
        async for chunk in self._orchestrator.stream(req):
            full_response.append(chunk.text)
            yield chunk

        # Persist complete assistant response after stream finishes
        complete_text = "".join(full_response)
        await self.conv_repo.add_message(
            UUID(conversation_id), role="assistant", content=complete_text, model_id=model or conv.model_id
        )