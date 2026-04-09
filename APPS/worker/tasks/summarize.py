"""
Summarization task.

Called when a conversation's message history exceeds 70% of the context window.
Summarizes the oldest N messages into a single synthetic summary message,
stores it in the conversation record, and truncates old messages.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from celery_app import celery_app

SUMMARY_PROMPT = """\
You are summarizing a conversation for memory compression. 
Create a concise summary (max 200 words) of the key points, decisions, and context 
from the following conversation excerpt. Write in third person past tense.
Preserve: important facts, user preferences, decisions made, and any technical details.

Conversation:
{conversation_text}

Summary:"""


@celery_app.task(
    name="tasks.summarize.summarize_conversation",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    queue="summarize",
)
def summarize_conversation(self, conversation_id: str, messages_to_summarize: int = 10):
    asyncio.run(_summarize_async(self, conversation_id, messages_to_summarize))


async def _summarize_async(task, conversation_id: str, messages_to_summarize: int):
    from db.session import AsyncSessionLocal
    from db.models.conversation import Conversation, Message, MessageRoleEnum
    from sqlalchemy import select, delete

    async with AsyncSessionLocal() as db:
        # Load conversation
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        if not conv:
            return

        # Load oldest N messages
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(messages_to_summarize)
        )
        messages = msg_result.scalars().all()
        if len(messages) < 2:
            return

        # Build conversation text
        conversation_text = "\n".join(
            f"{m.role.value.upper()}: {m.content[:500]}"
            for m in messages
        )

        # Generate summary
        summary = await _generate_summary(conversation_text)
        if not summary:
            return

        # Prepend to existing summary if one exists
        existing_summary = conv.summary or ""
        if existing_summary:
            conv.summary = f"{existing_summary}\n\n[Earlier context]: {summary}"
        else:
            conv.summary = summary

        # Delete the summarized messages (keep the most recent ones)
        message_ids = [m.id for m in messages]
        await db.execute(
            delete(Message).where(Message.id.in_(message_ids))
        )

        await db.commit()
        print(f"[Summarize] Summarized {len(messages)} messages for conversation {conversation_id}")


async def _generate_summary(conversation_text: str) -> str:
    """Call LLM to generate a summary."""
    from core.config import settings

    prompt = SUMMARY_PROMPT.format(conversation_text=conversation_text[:3000])

    try:
        if settings.openai_api_key:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.2,
            )
            return (response.choices[0].message.content or "").strip()

        elif settings.anthropic_api_key:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.content[0].text if response.content else "").strip()

        return ""
    except Exception as exc:
        print(f"[Summarize] Summary generation failed: {exc}")
        return ""