"""
Semantic chunker — highest quality, slowest.
Groups semantically similar sentences together using cosine similarity
of sentence embeddings. Falls back to fixed chunking if embeddings fail.
"""
import asyncio
from typing import Optional


async def chunk_text_async(
    text: str,
    chunk_size: int = 512,
    similarity_threshold: float = 0.75,
    chars_per_token: int = 4,
) -> list[str]:
    """
    Split text into semantically coherent chunks.

    Args:
        text:                 Input text.
        chunk_size:           Max tokens per chunk.
        similarity_threshold: Cosine similarity threshold to merge sentences.
        chars_per_token:      Char-to-token ratio.

    Returns:
        List of semantically grouped chunk strings.
    """
    if not text or not text.strip():
        return []

    # Step 1: Split into sentences
    from chunkers.sentence import _split_sentences
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return [text.strip()] if text.strip() else []

    # Step 2: Embed all sentences
    embeddings = await _embed_sentences(sentences)
    if not embeddings or all(e is None for e in embeddings):
        # Fallback to fixed chunking
        from chunkers.fixed import chunk_text
        return chunk_text(text, chunk_size=chunk_size)

    # Step 3: Greedily group consecutive similar sentences
    max_chars = chunk_size * chars_per_token
    chunks: list[str] = []
    current_group: list[str] = [sentences[0]]
    current_len = len(sentences[0])

    for i in range(1, len(sentences)):
        sentence = sentences[i]
        sentence_len = len(sentence)

        # Check similarity with previous sentence
        prev_emb = embeddings[i - 1]
        curr_emb = embeddings[i]
        similar = (
            prev_emb is not None
            and curr_emb is not None
            and _cosine_similarity(prev_emb, curr_emb) >= similarity_threshold
        )

        if similar and current_len + sentence_len <= max_chars:
            current_group.append(sentence)
            current_len += sentence_len
        else:
            if current_group:
                chunks.append(" ".join(current_group).strip())
            current_group = [sentence]
            current_len = sentence_len

    if current_group:
        chunks.append(" ".join(current_group).strip())

    return [c for c in chunks if c]


def chunk_text(text: str, chunk_size: int = 512, **kwargs) -> list[str]:
    """Sync wrapper — runs async version in event loop."""
    return asyncio.run(chunk_text_async(text, chunk_size=chunk_size, **kwargs))


async def _embed_sentences(sentences: list[str]) -> list[Optional[list[float]]]:
    """Embed sentences using OpenAI text-embedding-3-small."""
    from core.config import settings
    if not settings.openai_api_key:
        return [None] * len(sentences)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=sentences,
        )
        return [item.embedding for item in response.data]
    except Exception as exc:
        print(f"[Chunker/Semantic] Embedding failed: {exc}")
        return [None] * len(sentences)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)