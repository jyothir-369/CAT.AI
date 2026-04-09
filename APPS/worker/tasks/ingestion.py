"""
Ingestion task — parse → clean → chunk → embed → store pipeline.

Flow:
  1. Pick up file record (status=pending)
  2. Download from S3
  3. Parse text with appropriate parser
  4. Clean text
  5. Chunk text
  6. Embed chunks (OpenAI text-embedding-3-small)
  7. Store DocumentChunk rows
  8. Update file status → ready / failed
  9. Notify user
"""
import asyncio
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from celery import shared_task

from celery_app import celery_app


@celery_app.task(
    name="tasks.ingestion.ingest_file",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="ingestion",
)
def ingest_file(self, file_id: str, kb_id: Optional[str] = None):
    """
    Entry point: called after a file is uploaded to S3.
    Runs the full ingestion pipeline synchronously inside Celery.
    """
    asyncio.run(_ingest_file_async(self, file_id, kb_id))


async def _ingest_file_async(task, file_id: str, kb_id: Optional[str]):
    from db.session import AsyncSessionLocal
    from db.models.knowledge import File, FileStatusEnum, KnowledgeBase, Document, DocumentChunk
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # 1. Load file record
        result = await db.execute(select(File).where(File.id == file_id))
        file_record = result.scalar_one_or_none()
        if not file_record:
            print(f"[Ingestion] File {file_id} not found — skipping")
            return

        file_record.status = FileStatusEnum.processing
        await db.commit()

        try:
            # 2. Download from S3
            raw_bytes = await _download_from_s3(file_record.s3_key)

            # 3. Parse
            text = await _parse(raw_bytes, file_record.filename, file_record.mime_type or "")

            # 4. Clean
            text = _clean_text(text)

            if not text.strip():
                raise ValueError("Parsed text is empty — check file format")

            # 5. Chunk
            from chunkers.fixed import chunk_text
            chunks = chunk_text(text, chunk_size=512, overlap=50)

            # 6. Get or create Knowledge Base
            target_kb_id = kb_id or file_record.knowledge_base_id
            if not target_kb_id:
                # Auto-create a KB for this org
                kb = KnowledgeBase(
                    org_id=file_record.org_id,
                    name=f"Auto KB — {file_record.filename}",
                    embedding_model="text-embedding-3-small",
                    chunk_strategy="fixed",
                )
                db.add(kb)
                await db.flush()
                target_kb_id = kb.id
                file_record.knowledge_base_id = target_kb_id

            # 7. Create Document record
            doc = Document(
                kb_id=target_kb_id,
                file_id=file_id,
                title=file_record.filename,
                char_count=len(text),
                chunk_count=len(chunks),
                status="ready",
            )
            db.add(doc)
            await db.flush()

            # 8. Embed + store chunks
            embeddings = await _embed_chunks(chunks)
            for idx, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
                chunk = DocumentChunk(
                    document_id=doc.id,
                    kb_id=target_kb_id,
                    content=chunk_text_val,
                    embedding_json=json.dumps(embedding) if embedding else None,
                    chunk_index=idx,
                    token_count=len(chunk_text_val) // 4,
                )
                db.add(chunk)

            # 9. Update file + KB stats
            file_record.status = FileStatusEnum.ready
            kb_result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id == target_kb_id)
            )
            kb_obj = kb_result.scalar_one_or_none()
            if kb_obj:
                kb_obj.doc_count = (kb_obj.doc_count or 0) + 1

            await db.commit()
            print(f"[Ingestion] ✅ File {file_id} ingested — {len(chunks)} chunks created")

        except Exception as exc:
            file_record.status = FileStatusEnum.failed
            file_record.error_message = str(exc)[:1024]
            await db.commit()
            print(f"[Ingestion] ❌ File {file_id} failed: {exc}")
            raise task.retry(exc=exc)


async def _download_from_s3(s3_key: str) -> bytes:
    """Download file bytes from S3. Returns empty bytes in dev if AWS not configured."""
    from core.config import settings
    if not settings.aws_access_key_id:
        print(f"[Ingestion] AWS not configured — returning stub bytes for key: {s3_key}")
        return b"Stub content for development. Configure AWS_ACCESS_KEY_ID to use real S3."
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        obj = s3.get_object(Bucket=settings.s3_bucket_files, Key=s3_key)
        return obj["Body"].read()
    except Exception as exc:
        print(f"[Ingestion] S3 download failed for {s3_key}: {exc}")
        return b""


async def _parse(raw_bytes: bytes, filename: str, mime_type: str) -> str:
    """Route to the appropriate parser based on file extension / MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf" or "pdf" in mime_type:
        from parsers.pdf import parse_pdf
        return parse_pdf(raw_bytes)

    if ext in ("docx", "doc") or "word" in mime_type:
        from parsers.docx import parse_docx
        return parse_docx(raw_bytes)

    if ext in ("csv", "xlsx", "xls") or "spreadsheet" in mime_type or "csv" in mime_type:
        from parsers.csv_xlsx import parse_tabular
        return parse_tabular(raw_bytes, ext)

    # Plain text fallback
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1", errors="replace")


def _clean_text(text: str) -> str:
    """Remove excessive whitespace, fix encoding artifacts."""
    import re
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


async def _embed_chunks(chunks: list[str]) -> list[Optional[list[float]]]:
    """
    Embed a list of text chunks using OpenAI text-embedding-3-small.
    Returns a list of float vectors (or None per chunk on failure).
    """
    from core.config import settings
    if not settings.openai_api_key:
        print("[Ingestion] OpenAI not configured — skipping embeddings")
        return [None] * len(chunks)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Batch in groups of 100 (OpenAI limit)
        batch_size = 100
        all_embeddings: list[Optional[list[float]]] = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=batch,
            )
            all_embeddings.extend([item.embedding for item in response.data])

        return all_embeddings
    except Exception as exc:
        print(f"[Ingestion] Embedding failed: {exc}")
        return [None] * len(chunks)