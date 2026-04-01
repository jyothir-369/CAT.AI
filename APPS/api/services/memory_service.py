from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.repos.memory_repo import MemoryRepo
from core.exceptions import NotFoundError


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MemoryRepo(db)

    async def list(self, user_id: str, org_id: str) -> list:
        return await self.repo.list_by_user(UUID(user_id), UUID(org_id))

    async def delete(self, user_id: str, memory_id: str) -> None:
        deleted = await self.repo.delete(UUID(memory_id), UUID(user_id))
        if not deleted:
            raise NotFoundError("Memory", memory_id)

    async def clear_all(self, user_id: str, org_id: str) -> int:
        return await self.repo.delete_all(UUID(user_id), UUID(org_id))

    async def extract_and_store(
        self,
        user_id: str,
        org_id: str,
        user_message: str,
        assistant_response: str,
        conversation_id: str | None = None,
    ) -> list:
        """
        Extracts memorable facts from an exchange and stores them.
        Called as a background task after each assistant response.

        Production: send exchange to cheap model with extraction prompt,
        parse JSON array of facts, embed each, dedup via cosine similarity.
        """
        # Mock extraction — replace with real LLM call
        facts = _mock_extract_facts(user_message, assistant_response)
        saved = []
        for fact in facts:
            mem = await self.repo.create(
                org_id=UUID(org_id),
                user_id=UUID(user_id),
                content=fact,
                importance_score=0.6,
                source_conversation_id=UUID(conversation_id) if conversation_id else None,
            )
            saved.append(mem)
        return saved

    async def get_relevant(self, user_id: str, org_id: str, query: str, limit: int = 5) -> list[str]:
        """
        Returns top-k semantically relevant memory strings for prompt injection.
        Production: embed query → cosine search with recency weighting.
        score = 0.7 * similarity + 0.3 * recency_decay
        """
        memories = await self.repo.list_by_user(UUID(user_id), UUID(org_id), limit=limit)
        return [m.content for m in memories]


def _mock_extract_facts(user_msg: str, assistant_msg: str) -> list[str]:
    """Placeholder — real version calls an LLM with a memory extraction prompt."""
    facts = []
    lower = user_msg.lower()
    if "my name is" in lower:
        facts.append(f"User stated their name in a conversation.")
    if "i prefer" in lower or "i like" in lower:
        facts.append(f"User expressed a preference.")
    return facts