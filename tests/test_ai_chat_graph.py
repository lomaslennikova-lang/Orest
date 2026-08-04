from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from psycopg import OperationalError

from app.ai_chat.graph import AIChatProviderError, run_chat_turn


class FlakyGraph:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _graph_input, _graph_config):
        self.calls += 1
        if self.calls == 1:
            raise OperationalError("connection was replaced")
        return {"response": "Готово."}


class ChatGraphRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_once_after_transient_postgres_error(self):
        graph = FlakyGraph()

        with patch("app.ai_chat.graph.asyncio.sleep", new=AsyncMock()) as sleep:
            response = await run_chat_turn(graph, uuid4(), "Покажи витрати")

        self.assertEqual(response, "Готово.")
        self.assertEqual(graph.calls, 2)
        sleep.assert_awaited_once_with(0.2)

    async def test_raises_provider_error_when_graph_exhausts_gemini_retries(self):
        graph = AsyncMock()
        graph.ainvoke.return_value = {"response": "", "provider_unavailable": True}

        with self.assertRaises(AIChatProviderError):
            await run_chat_turn(graph, uuid4(), "Покажи витрати")
