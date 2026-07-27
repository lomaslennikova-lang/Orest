from __future__ import annotations

import unittest

from app.ai_chat.gemini import AIChatLLMError, _parse_turn


class GeminiTurnParsingTests(unittest.TestCase):
    def test_parses_text_and_function_call(self):
        turn = _parse_turn(
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"text": "Перевіряю дані."},
                                {
                                    "functionCall": {
                                        "name": "get_transactions_summary",
                                        "args": {"date_from": "2026-06-01"},
                                    }
                                },
                            ],
                        }
                    }
                ]
            }
        )

        self.assertEqual(turn.text, "Перевіряю дані.")
        self.assertEqual(turn.tool_calls[0].name, "get_transactions_summary")
        self.assertEqual(turn.tool_calls[0].arguments, {"date_from": "2026-06-01"})

    def test_rejects_response_without_text_or_tools(self):
        with self.assertRaises(AIChatLLMError):
            _parse_turn({"candidates": [{"content": {"parts": [{}]}}]})
