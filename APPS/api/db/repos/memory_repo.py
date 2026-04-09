"""
Memory repository — cosine search, deduplication, recency scoring.
Production path: replace Python-side cosine with pgvector ORDER BY <=> operator.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.memory import Memory


class MemoryRepo:

    async def list_for_user(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        limit: int = 200,
    ) -> list[Memory]:
        result = await db.execute(
            select(Memory)
            .where(Memory.org_id == org_id, Memory.user_id == user_id)
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        query_embedding: list[float],
        top_k: int = 5,
        recency_weight: float = 0.3,
    ) -> list[Memory]:
        """
        Retrieve top-k memories by weighted score:
            score = 0.7 * cosine_similarity + 0.3 * recency_decay

        MVP: Python-side scoring over last 200 memories.
        Production: pgvector ANN index + SQL ORDER BY hybrid score.
        """
        memories = await self.list_for_user(db, org_id, user_id, limit=200)
        if not memories:
            return []

        now = datetime.now(timezone.utc)
        scored: list[tuple[float, Memory]] = []

        for mem in memories:
            sim = 0.0
            if mem.embedding_json and query_embedding:
                try:
                    vec = json.loads(mem.embedding_json)
                    sim = _cosine_similarity(query_embedding, vec)
                except Exception:
                    pass

            # Recency decay: exponential decay over 30 days
            age_days = max(
                0.0,
                (now - mem.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
                if mem.created_at.tzinfo is None
                else (now - mem.created_at).total_seconds() / 86400,
            )
            recency = max(0.0, 1.0 - age_days / 30.0)

            score = (1 - recency_weight) * sim + recency_weight * recency
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    async def store(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        content: str,
        embedding: Optional[list[float]] = None,
        source_conversation_id: Optional[str] = None,
        importance_score: float = 1.0,
    ) -> Memory:
        memory = Memory(
            org_id=org_id,
            user_id=user_id,
            content=content,
            embedding_json=json.dumps(embedding) if embedding else None,
            importance_score=importance_score,
            source_conversation_id=source_conversation_id,
        )
        db.add(memory)
        await db.flush()
        return memory

    async def is_duplicate(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        embedding: list[float],
        threshold: float = 0.95,
    ) -> bool:
        """Return True if a very similar memory already exists."""
        memories = await self.list_for_user(db, org_id, user_id, limit=500)
        for mem in memories:
            if not mem.embedding_json:
                continue
            try:
                vec = json.loads(mem.embedding_json)
                if _cosine_similarity(embedding, vec) >= threshold:
                    return True
            except Exception:
                continue
        return False

    async def delete_one(
        self, db: AsyncSession, memory_id: str, user_id: str
    ) -> bool:
        result = await db.execute(
            select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        )
        mem = result.scalar_one_or_none()
        if not mem:
            return False
        await db.delete(mem)
        return True

    async def delete_all_for_user(
        self, db: AsyncSession, org_id: str, user_id: str
    ) -> int:
        result = await db.execute(
            select(Memory).where(Memory.org_id == org_id, Memory.user_id == user_id)
        )
        memories = result.scalars().all()
        count = len(memories)
        for mem in memories:
            await db.delete(mem)
        return count


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


memory_repo = MemoryRepo()