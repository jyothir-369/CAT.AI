from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.repos.knowledge_repo import KnowledgeRepo
from core.exceptions import NotFoundError


class RAGService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = KnowledgeRepo(db)

    # ── Knowledge bases ───────────────────────────────────────────────────────

    async def list_knowledge_bases(self, org_id: str) -> list:
        return await self.repo.list_kbs(UUID(org_id))

    async def create_knowledge_base(self, org_id: str, name: str, description: str | None = None):
        return await self.repo.create_kb(UUID(org_id), name=name, description=description)

    async def get_knowledge_base(self, org_id: str, kb_id: str):
        kb = await self.repo.get_kb(UUID(kb_id), UUID(org_id))
        if not kb:
            raise NotFoundError("KnowledgeBase", kb_id)
        return kb

    # ── Files ─────────────────────────────────────────────────────────────────

    async def list_files(self, org_id: str) -> list:
        return await self.repo.list_files(UUID(org_id))

    async def create_file_record(
        self, org_id: str, user_id: str, filename: str, mime_type: str, size_bytes: int
    ):
        """
        Creates a DB record and returns an S3 presigned URL for direct upload.
        Worker picks up the file after upload and runs the ingestion pipeline.
        """
        import uuid as uuid_lib
        s3_key = f"uploads/{org_id}/{uuid_lib.uuid4()}/{filename}"
        file_rec = await self.repo.create_file_record(
            org_id=UUID(org_id),
            user_id=UUID(user_id),
            filename=filename,
            mime_type=mime_type,
            s3_key=s3_key,
            size_bytes=size_bytes,
        )
        # Mock presigned URL — replace with boto3 generate_presigned_post()
        presigned_url = f"https://s3.amazonaws.com/cat-ai-files/{s3_key}?mock=true"
        return {"file": file_rec, "upload_url": presigned_url, "s3_key": s3_key}

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def query(self, org_id: str, kb_id: str, query: str, top_k: int = 5) -> list[dict]:
        """
        Hybrid retrieval: vector similarity (pgvector) + BM25 keyword search.
        Production: embed query → cosine search → merge BM25 results → rerank.
        """
        kb = await self.get_knowledge_base(org_id, kb_id)
        chunks = await self.repo.search_chunks(kb.id, query_text=query, limit=top_k)
        return [
            {
                "content": c.content,
                "chunk_index": c.chunk_index,
                "document_id": str(c.document_id),
                "metadata": c.metadata_,
            }
            for c in chunks
        ]

    async def retrieve_for_prompt(self, org_id: str, kb_id: str, query: str, top_k: int = 5) -> list[str]:
        """Returns plain text chunks ready to inject into the prompt."""
        results = await self.query(org_id, kb_id, query, top_k=top_k)
        return [r["content"] for r in results]