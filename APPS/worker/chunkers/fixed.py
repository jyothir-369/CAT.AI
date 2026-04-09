"""
Fixed-size chunker — default strategy.
Splits text into overlapping chunks of ~512 tokens with 50-token overlap.
Uses character-based approximation (1 token ≈ 4 chars) to avoid tiktoken dependency.
"""


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    chars_per_token: int = 4,
) -> list[str]:
    """
    Split text into overlapping fixed-size chunks.

    Args:
        text:             Input text to chunk.
        chunk_size:       Target chunk size in tokens.
        overlap:          Overlap between consecutive chunks in tokens.
        chars_per_token:  Character-to-token ratio (default 4).

    Returns:
        List of text chunk strings.
    """
    if not text or not text.strip():
        return []

    chunk_chars = chunk_size * chars_per_token
    overlap_chars = overlap * chars_per_token
    step = chunk_chars - overlap_chars

    if step <= 0:
        step = chunk_chars

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_chars, text_len)
        chunk = text[start:end].strip()

        # Try to break at a sentence or paragraph boundary to avoid mid-sentence splits
        if end < text_len:
            # Look back up to 200 chars for a good break point
            search_start = max(end - 200, start)
            for boundary in ("\n\n", "\n", ". ", "! ", "? ", "; ", ", "):
                idx = text.rfind(boundary, search_start, end)
                if idx > start:
                    end = idx + len(boundary)
                    chunk = text[start:end].strip()
                    break

        if chunk:
            chunks.append(chunk)

        start = start + step
        # Don't go backwards if we broke early at a boundary
        if end > start:
            start = end - overlap_chars
            if start < 0:
                start = 0

    # Remove duplicates while preserving order (can happen with very short texts)
    seen = set()
    unique_chunks = []
    for c in chunks:
        key = c[:50]
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    return unique_chunks