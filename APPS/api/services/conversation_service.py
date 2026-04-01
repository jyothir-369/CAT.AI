from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.repos.conversation_repo import ConversationRepo
from core.exceptions import NotFoundError
from core.config import settings


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ConversationRepo(db)

    async def list(self, org_id: str, user_id: str, limit: int = 20, offset: int = 0) -> list:
        return await self.repo.list_by_org(UUID(org_id), UUID(user_id), limit=limit, offset=offset)

    async def create(
        self,
        org_id: str,
        user_id: str,
        model_id: str | None = None,
        title: str | None = None,
        system_prompt: str | None = None,
    ):
        return await self.repo.create(
            org_id=UUID(org_id),
            user_id=UUID(user_id),
            model_id=model_id or settings.DEFAULT_MODEL,
            title=title,
            system_prompt=system_prompt,
        )

    async def get(self, org_id: str, conversation_id: str):
        conv = await self.repo.get_by_id(UUID(conversation_id), UUID(org_id))
        if not conv:
            raise NotFoundError("Conversation", conversation_id)
        return conv

    async def get_messages(self, org_id: str, conversation_id: str, limit: int = 100) -> list:
        conv = await self.get(org_id, conversation_id)
        return await self.repo.get_messages(conv.id, limit=limit)

    async def delete(self, org_id: str, user_id: str, conversation_id: str) -> None:
        conv = await self.get(org_id, conversation_id)
        if str(conv.user_id) != user_id:
            from core.exceptions import InsufficientPermissionsError
            raise InsufficientPermissionsError()
        await self.repo.delete(conv)

    async def summarize(self, org_id: str, conversation_id: str) -> str:
        """
        Summarise older messages to free up context window budget.
        In production: call cheap model (Groq Llama3) to generate summary.
        """
        conv = await self.get(org_id, conversation_id)
        messages = await self.repo.get_messages(conv.id)
        if len(messages) < 10:
            return conv.summary or ""

        # Placeholder summary — replace with real LLM call
        summary = f"[Summary of {len(messages)} messages in conversation '{conv.title or conversation_id}']"
        await self.repo.update_summary(conv, summary)
        return summary