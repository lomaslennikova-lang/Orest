from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from pydantic import ValidationError

from app.api import app, create_ai_conversation
from app.ai_chat.schemas import ChatRequest


class AIChatRouteTests(unittest.TestCase):
    def test_protected_chat_routes_are_registered(self):
        paths = {route.path for route in app.routes}
        self.assertTrue(
            {
                "/api/ai/chat",
                "/api/ai/attachments",
                "/api/ai/actions/{action_id}",
                "/api/ai/actions/{action_id}/confirm",
                "/api/ai/actions/{action_id}/cancel",
                "/api/ai/conversations",
                "/api/ai/conversations/last",
                "/api/ai/conversations/{conversation_id}/messages",
                "/api/admin/google-drive/connect",
                "/api/admin/google-drive/callback",
            }
            <= paths
        )

    def test_chat_request_allows_clarification_for_existing_receipt(self):
        request = ChatRequest(
            message="Сума в чеку становить 500 грн.",
            clarification_action_id=uuid4(),
        )
        self.assertIsNotNone(request.clarification_action_id)

        with self.assertRaises(ValidationError):
            ChatRequest(
                message="Уточнення",
                attachment_id=uuid4(),
                clarification_action_id=uuid4(),
            )


class CreateAIConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_an_empty_conversation_without_loading_or_deleting_history(self):
        conversation = SimpleNamespace(
            id=uuid4(),
            owner_user_id=42,
            title=None,
            updated_at=datetime.now(timezone.utc),
        )
        session = AsyncMock()
        session_context = AsyncMock()
        session_context.__aenter__.return_value = session

        with (
            patch("app.api.AsyncSessionLocal", return_value=session_context),
            patch(
                "app.api.get_admin_chat_user",
                new=AsyncMock(return_value=SimpleNamespace(id=42)),
            ),
            patch("app.api.create_conversation", new=AsyncMock(return_value=conversation)) as create,
        ):
            result = await create_ai_conversation({"username": "admin"})

        create.assert_awaited_once_with(session, owner_user_id=42)
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(conversation)
        self.assertEqual(result.id, conversation.id)
