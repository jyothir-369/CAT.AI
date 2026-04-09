"""
Knowledge base repository — data access for KBs, documents, chunks.
"""
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.knowledge import KnowledgeBase, Document, DocumentChunk, File


class KnowledgeRepo:

    async def get_kb(
        self, db: AsyncSession, kb_id: str, org_id: str
    ) -> Optional[KnowledgeBase]:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_kbs(self, db: AsyncSession, org_id: str) -> list[KnowledgeBase]:
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.org_id == org_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_chunks_for_kb(
        self,
        db: AsyncSession,
        kb_id: str,
        limit: int = 100,
    ) -> list[DocumentChunk]:
        result = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.kb_id == kb_id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def cosine_search(
        self,
        db: AsyncSession,
        kb_id: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[DocumentChunk]:
        """
        MVP: load chunks and compute cosine similarity in Python.
        Production: use pgvector ORDER BY embedding <=> $1 LIMIT $2
        """
        chunks = await self.get_chunks_for_kb(db, kb_id, limit=1000)
        if not chunks:
            return []

        scored = []
        for chunk in chunks:
            if not chunk.embedding_json:
                continue
            try:
                vec = json.loads(chunk.embedding_json)
                sim = _cosine_similarity(query_embedding, vec)
                scored.append((sim, chunk))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    async def get_document(
        self, db: AsyncSession, doc_id: str
    ) -> Optional[Document]:
        result = await db.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


knowledge_repo = KnowledgeRepo()