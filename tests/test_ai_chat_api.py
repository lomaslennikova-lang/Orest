from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.api import app
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
