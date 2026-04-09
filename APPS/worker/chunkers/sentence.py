"""
Sentence-boundary chunker — better for narrative text.
Splits on sentence boundaries, groups sentences until chunk_size is reached.
"""
import re


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap_sentences: int = 2,
    chars_per_token: int = 4,
) -> list[str]:
    """
    Split text into chunks that respect sentence boundaries.

    Args:
        text:               Input text.
        chunk_size:         Target chunk size in tokens.
        overlap_sentences:  Number of sentences to overlap between chunks.
        chars_per_token:    Character-to-token estimate.

    Returns:
        List of text chunk strings.
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    max_chars = chunk_size * chars_per_token
    chunks = []
    current_sentences: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # If a single sentence exceeds chunk size, force-include it alone
        if sentence_len > max_chars and not current_sentences:
            chunks.append(sentence.strip())
            continue

        if current_len + sentence_len > max_chars and current_sentences:
            # Flush current chunk
            chunks.append(" ".join(current_sentences).strip())
            # Keep last N sentences as overlap
            current_sentences = current_sentences[-overlap_sentences:] if overlap_sentences else []
            current_len = sum(len(s) for s in current_sentences)

        current_sentences.append(sentence)
        current_len += sentence_len

    # Flush remaining
    if current_sentences:
        chunks.append(" ".join(current_sentences).strip())

    return [c for c in chunks if c]


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex.
    Handles common abbreviations to avoid false splits.
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split on sentence-ending punctuation followed by whitespace or newline
    pattern = r"(?<=[.!?])\s+(?=[A-Z\"\'\(])"
    sentences = re.split(pattern, text)

    # Also split on double newlines (paragraph breaks)
    result = []
    for sent in sentences:
        parts = sent.split("\n\n")
        result.extend(p.strip() for p in parts if p.strip())

    return result