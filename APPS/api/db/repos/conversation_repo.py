"""
Conversation repository — all raw ORM queries for conversations and messages.
No business logic here — just data access.
"""
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.conversation import Conversation, Message, MessageRoleEnum


class ConversationRepo:

    async def get_by_id(
        self, db: AsyncSession, conversation_id: str, org_id: str
    ) -> Optional[Conversation]:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.org_id == org_id, Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        title: Optional[str] = None,
        model_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Conversation:
        conv = Conversation(
            org_id=org_id,
            user_id=user_id,
            title=title or "New Conversation",
            model_id=model_id,
            system_prompt=system_prompt,
        )
        db.add(conv)
        await db.flush()
        return conv

    async def delete(self, db: AsyncSession, conversation_id: str, org_id: str) -> bool:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.org_id == org_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return False
        await db.delete(conv)
        return True

    async def get_recent_messages(
        self,
        db: AsyncSession,
        conversation_id: str,
        limit: int = 20,
    ) -> list[Message]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        role: MessageRoleEnum,
        content: str,
        model_id: Optional[str] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_id=model_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
        )
        db.add(msg)
        await db.flush()
        return msg


conversation_repo = ConversationRepo()