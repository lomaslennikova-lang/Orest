from __future__ import annotations

import unittest

from app.api import app


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
