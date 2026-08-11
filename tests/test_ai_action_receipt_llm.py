from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app.ai_actions.receipt_llm import (
    ReceiptDraftLLMError,
    _analyse_receipt_sync,
    _parse_receipt_response,
)


def gemini_json_response(value: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": value}]}}]}


class ReceiptDraftParsingTests(unittest.TestCase):
    def test_parses_only_complete_expense_draft(self):
        turn = _parse_receipt_response(
            gemini_json_response(
                """{
                    "status": "pending_confirmation",
                    "message": "Підготовлено чернетку.",
                    "transactions": [{
                        "created_at": "2026-07-01T10:30:00Z",
                        "amount": "123.45",
                        "category": "Продукти",
                        "type": "expense"
                    }]
                }"""
            )
        )

        self.assertEqual(turn.result.status, "pending_confirmation")
        self.assertEqual(turn.result.transactions[0].type, "expense")

    def test_parses_partial_draft_with_clarification_issues(self):
        turn = _parse_receipt_response(
            gemini_json_response(
                '''{
                    "status":"needs_clarification",
                    "message":"Потрібно уточнити одну позицію.",
                    "transactions":[{
                        "created_at":"2026-07-01T10:30:00Z",
                        "amount":"123.45",
                        "category":"Продукти",
                        "type":"expense"
                    }],
                    "issues":[{
                        "line_number":2,
                        "category":null,
                        "amount":"200.00"
                    }]
                }'''
            )
        )
        self.assertEqual(turn.result.status, "needs_clarification")
        self.assertEqual(len(turn.result.transactions), 1)
        self.assertEqual(turn.result.issues[0].line_number, 2)

    def test_preserves_a_separate_transaction_for_each_receipt_position(self):
        turn = _parse_receipt_response(
            gemini_json_response(
                """{
                    "status": "pending_confirmation",
                    "message": "Підготовлено 3 позиції.",
                    "transactions": [
                        {"created_at":"2026-07-01T10:30:00Z","amount":"20.00","category":"Продукти","type":"expense"},
                        {"created_at":"2026-07-01T10:30:00Z","amount":"35.00","category":"Продукти","type":"expense"},
                        {"created_at":"2026-07-01T10:30:00Z","amount":"15.00","category":"Побутові товари","type":"expense"}
                    ]
                }"""
            )
        )

        self.assertEqual(len(turn.result.transactions), 3)
        self.assertEqual(
            [str(transaction.amount) for transaction in turn.result.transactions],
            ["20.00", "35.00", "15.00"],
        )

    def test_rejects_income_unknown_fields_and_incomplete_draft(self):
        for payload in (
            '{"status":"pending_confirmation","message":"x","transactions":[]}',
            '{"status":"needs_clarification","message":"x","transactions":[]}',
            '{"status":"pending_confirmation","message":"x","transactions":[{"created_at":"2026-07-01T00:00:00Z","amount":"1","category":"Food","type":"income"}]}',
            '{"status":"needs_clarification","message":"x","transactions":[],"secret":"no"}',
        ):
            with self.subTest(payload=payload), self.assertRaises(ReceiptDraftLLMError):
                _parse_receipt_response(gemini_json_response(payload))


class ReceiptDraftRetryTests(unittest.TestCase):
    @staticmethod
    def valid_response() -> io.BytesIO:
        return io.BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": (
                                            '{"status":"needs_clarification",'
                                            '"message":"Вкажіть суму.",'
                                            '"transactions":[],"issues":[{'
                                            '"line_number":1,"category":null,"amount":null}]}'
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode()
        )

    def call_receipt_model(self):
        return _analyse_receipt_sync(
            content=b"receipt",
            media_type="image/png",
            filename="receipt.png",
            user_message="Додай витрати.",
            timeout=1,
        )

    def test_retries_a_transient_gemini_503_then_returns_draft(self):
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
                "app.ai_actions.receipt_llm.urlopen",
                side_effect=[unavailable, self.valid_response()],
            ) as urlopen_mock,
            patch("app.ai_actions.receipt_llm.time.sleep") as sleep_mock,
        ):
            result = self.call_receipt_model()

        self.assertEqual(result.result.status, "needs_clarification")
        self.assertEqual(urlopen_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.5)
        unavailable.close()

    def test_does_not_retry_a_non_transient_gemini_error(self):
        invalid_request = HTTPError(
            "https://example.invalid",
            400,
            "Bad Request",
            None,
            io.BytesIO(),
        )
        with (
            patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=False),
            patch("app.ai_actions.receipt_llm.urlopen", side_effect=invalid_request) as urlopen_mock,
            patch("app.ai_actions.receipt_llm.time.sleep") as sleep_mock,
        ):
            with self.assertRaisesRegex(ReceiptDraftLLMError, "rejected"):
                self.call_receipt_model()

        self.assertEqual(urlopen_mock.call_count, 1)
        sleep_mock.assert_not_called()
        invalid_request.close()
