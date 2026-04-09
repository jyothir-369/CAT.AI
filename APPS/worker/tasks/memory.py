"""
Memory extraction task.

After each assistant response, this task:
  1. Loads the exchange (user message + assistant response)
  2. Sends to a cheap model (Groq / GPT-4o-mini) with a memory extraction prompt
  3. Embeds extracted facts
  4. Deduplicates against existing memories (cosine similarity > 0.95 → skip)
  5. Stores new memories in the memories table
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from celery_app import celery_app

EXTRACTION_PROMPT = """\
You are a memory extractor. Given the following conversation exchange, extract any facts, \
user preferences, stated constraints, decisions made, or important context that would be \
useful to remember in future conversations.

Return ONLY a JSON array of short fact strings. Return [] if nothing is worth remembering.
Example: ["User prefers Python over JavaScript", "User is building a SaaS product"]

Exchange:
User: {user_message}
Assistant: {assistant_message}

JSON array:"""


@celery_app.task(
    name="tasks.memory.extract_memories",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    queue="memory",
)
def extract_memories(self, message_id: str, org_id: str, user_id: str, conversation_id: str):
    asyncio.run(_extract_async(self, message_id, org_id, user_id, conversation_id))


async def _extract_async(task, message_id: str, org_id: str, user_id: str, conversation_id: str):
    from db.session import AsyncSessionLocal
    from db.models.conversation import Message, MessageRoleEnum
    from db.models.memory import Memory
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # 1. Load the assistant message and preceding user message
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(2)
        )
        messages = list(reversed(result.scalars().all()))

        user_msg = next((m for m in messages if m.role == MessageRoleEnum.user), None)
        asst_msg = next((m for m in messages if m.role == MessageRoleEnum.assistant), None)

        if not user_msg or not asst_msg:
            return

        # 2. Extract facts via LLM
        facts = await _extract_facts(user_msg.content, asst_msg.content)
        if not facts:
            return

        # 3. Embed facts
        embeddings = await _embed_texts(facts)

        # 4. Load existing memories for deduplication
        existing_result = await db.execute(
            select(Memory).where(Memory.org_id == org_id, Memory.user_id == user_id).limit(500)
        )
        existing_memories = existing_result.scalars().all()
        existing_vecs = []
        for mem in existing_memories:
            if mem.embedding_json:
                try:
                    existing_vecs.append((mem, json.loads(mem.embedding_json)))
                except Exception:
                    pass

        # 5. Store new (non-duplicate) memories
        stored = 0
        for fact, embedding in zip(facts, embeddings):
            if embedding and _is_duplicate(embedding, existing_vecs, threshold=0.95):
                continue

            memory = Memory(
                org_id=org_id,
                user_id=user_id,
                content=fact,
                embedding_json=json.dumps(embedding) if embedding else None,
                importance_score=1.0,
                source_conversation_id=conversation_id,
            )
            db.add(memory)
            stored += 1

        if stored:
            await db.commit()
            print(f"[Memory] Stored {stored} new memories for user {user_id}")


async def _extract_facts(user_message: str, assistant_message: str) -> list[str]:
    """Call LLM to extract memorable facts from the exchange."""
    from core.config import settings

    prompt = EXTRACTION_PROMPT.format(
        user_message=user_message[:500],
        assistant_message=assistant_message[:500],
    )

    try:
        if settings.openai_api_key:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.1,
            )
            raw = response.choices[0].message.content or "[]"
        else:
            return []

        # Parse JSON array
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        facts = json.loads(raw)
        if isinstance(facts, list):
            return [str(f).strip() for f in facts if f and len(str(f).strip()) > 5]
        return []
    except Exception as exc:
        print(f"[Memory] Extraction failed: {exc}")
        return []


async def _embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Embed facts using OpenAI text-embedding-3-small."""
    from core.config import settings
    if not settings.openai_api_key or not texts:
        return [None] * len(texts)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]
    except Exception as exc:
        print(f"[Memory] Embedding failed: {exc}")
        return [None] * len(texts)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _is_duplicate(
    embedding: list[float],
    existing: list[tuple],
    threshold: float = 0.95,
) -> bool:
    """Return True if this embedding is too similar to an existing memory."""
    for _, existing_vec in existing:
        if _cosine_similarity(embedding, existing_vec) >= threshold:
            return True
    return False