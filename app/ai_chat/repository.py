"""Database access for AI-chat persistence.

Every lookup accepts the authenticated owner's database ID. This keeps
conversation ownership checks in the repository rather than trusting client
input when HTTP routes are added later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_chat.schemas import ChatMessageCreate
from app.models import AIConversation, AIMessage


async def create_conversation(
    session: AsyncSession,
    *,
    owner_user_id: int,
    title: str | None = None,
) -> AIConversation:
    conversation = AIConversation(owner_user_id=owner_user_id, title=title)
    session.add(conversation)
    await session.flush()
    return conversation


async def get_owned_conversation(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    owner_user_id: int,
) -> AIConversation | None:
    result = await session.execute(
        select(AIConversation).where(
            AIConversation.id == conversation_id,
            AIConversation.owner_user_id == owner_user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_last_owned_conversation(
    session: AsyncSession,
    *,
    owner_user_id: int,
) -> AIConversation | None:
    result = await session.execute(
        select(AIConversation)
        .where(AIConversation.owner_user_id == owner_user_id)
        .order_by(desc(AIConversation.updated_at), desc(AIConversation.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def add_message(
    session: AsyncSession,
    *,
    conversation: AIConversation,
    payload: ChatMessageCreate,
) -> AIMessage:
    message = AIMessage(conversation_id=conversation.id, **payload.model_dump())
    session.add(message)
    conversation.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return message


async def get_recent_messages(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    limit: int = 50,
) -> list[AIMessage]:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    result = await session.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(desc(AIMessage.id))
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))
