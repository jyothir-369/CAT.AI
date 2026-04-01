import asyncio
import logging

logger = logging.getLogger(__name__)

# Simple keyword blocklist — replace with OpenAI Moderation API or a local classifier
_BLOCKLIST = frozenset([
    "ignore previous instructions",
    "disregard your system prompt",
    "you are now",
    "jailbreak",
])


class ModerationFlag:
    def __init__(self, flagged: bool, reason: str | None = None, categories: list[str] | None = None):
        self.flagged = flagged
        self.reason = reason
        self.categories = categories or []


async def moderate_input(text: str, org_id: str | None = None) -> ModerationFlag:
    """
    Non-blocking input moderation.
    In production: replace body with OpenAI Moderation API call.
    """
    text_lower = text.lower()
    for phrase in _BLOCKLIST:
        if phrase in text_lower:
            logger.warning("Moderation flag — prompt injection attempt", extra={"org_id": org_id})
            return ModerationFlag(flagged=True, reason="prompt_injection", categories=["injection"])

    # Simulate async moderation call latency (remove in production)
    await asyncio.sleep(0)
    return ModerationFlag(flagged=False)


async def moderate_output(text: str, org_id: str | None = None) -> ModerationFlag:
    """
    Post-response moderation — runs asynchronously after stream completes.
    Flags are logged and surfaced to admins; responses are never blocked mid-stream.
    """
    await asyncio.sleep(0)
    return ModerationFlag(flagged=False)


def log_flag(flag: ModerationFlag, context: dict) -> None:
    if flag.flagged:
        logger.warning(
            "Content moderation flag",
            extra={"reason": flag.reason, "categories": flag.categories, **context},
        )