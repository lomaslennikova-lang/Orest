from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app.ai_chat.gemini import (
    AIChatLLMError,
    _function_declarations,
    _generate_chat_turn_sync,
    _parse_turn,
)


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

    def test_function_schemas_exclude_gemini_unsupported_fields(self):
        declarations = _function_declarations()
        self.assertTrue(declarations)
        for declaration in declarations:
            self.assertNotIn("additionalProperties", declaration["parameters"])


class GeminiRetryTests(unittest.TestCase):
    @staticmethod
    def valid_response() -> io.BytesIO:
        return io.BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": "Готово."}]}}
                    ]
                }
            ).encode()
        )

    def test_retries_a_transient_gemini_503_then_returns_chat_turn(self):
        unavailable = HTTPError(
            "https://example.invalid",
            503,
            "Unavailable",
            None,
            io.BytesIO(),
        )
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=False),  # pragma: allowlist secret
            patch(
                "app.ai_chat.gemini.urlopen",
                side_effect=[unavailable, self.valid_response()],
            ) as urlopen_mock,
            patch("app.ai_chat.gemini.time.sleep") as sleep_mock,
        ):
            turn = _generate_chat_turn_sync(
                [{"role": "user", "parts": [{"text": "Покажи витрати."}]}],
                timeout=1,
            )

        self.assertEqual(turn.text, "Готово.")
        self.assertEqual(urlopen_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.5)
        unavailable.close()
