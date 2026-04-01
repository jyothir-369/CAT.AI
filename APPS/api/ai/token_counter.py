from ai.providers.base import ChatMessage

# tiktoken model name → encoding map
_ENCODING_MAP = {
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}

# Per-model token costs (USD per 1k tokens)
COST_TABLE: dict[str, dict[str, float]] = {
    "gpt-4o":           {"in": 0.005,  "out": 0.015},
    "gpt-4o-mini":      {"in": 0.00015,"out": 0.0006},
    "gpt-4-turbo":      {"in": 0.01,   "out": 0.03},
    "claude-opus-4-6":  {"in": 0.015,  "out": 0.075},
    "claude-sonnet-4-6":{"in": 0.003,  "out": 0.015},
    "claude-haiku-4-5-20251001": {"in": 0.00025, "out": 0.00125},
    "llama3-70b-8192":  {"in": 0.00059,"out": 0.00079},
    "gemini-1.5-pro":   {"in": 0.0035, "out": 0.0105},
}


def count_tokens(messages: list[ChatMessage], model: str) -> int:
    """Count tokens using tiktoken when available, char estimate otherwise."""
    encoding_name = _ENCODING_MAP.get(model)
    if encoding_name:
        try:
            import tiktoken
            enc = tiktoken.get_encoding(encoding_name)
            # 4 overhead tokens per message (role + framing)
            return sum(len(enc.encode(m.content)) + 4 for m in messages) + 2
        except Exception:
            pass
    # Fallback: 1 token ≈ 4 characters
    return sum(len(m.content) for m in messages) // 4


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return estimated USD cost for a completion."""
    rates = COST_TABLE.get(model, {"in": 0.002, "out": 0.002})
    return (tokens_in / 1000) * rates["in"] + (tokens_out / 1000) * rates["out"]


def tokens_remaining(model: str, used: int) -> int:
    """Return approximate remaining context window."""
    context_windows = {
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "claude-opus-4-6": 200_000,
        "claude-sonnet-4-6": 200_000,
        "claude-haiku-4-5-20251001": 200_000,
        "llama3-70b-8192": 8_192,
        "gemini-1.5-pro": 1_000_000,
    }
    window = context_windows.get(model, 8_192)
    return max(0, window - used)