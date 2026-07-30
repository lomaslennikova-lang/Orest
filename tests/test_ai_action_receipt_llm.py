from __future__ import annotations

import unittest

from app.ai_actions.receipt_llm import ReceiptDraftLLMError, _parse_receipt_response


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

    def test_parses_clarification_without_transactions(self):
        turn = _parse_receipt_response(
            gemini_json_response(
                '{"status":"needs_clarification","message":"Вкажіть суму в UAH.","transactions":[]}'
            )
        )
        self.assertEqual(turn.result.status, "needs_clarification")

    def test_rejects_income_unknown_fields_and_incomplete_draft(self):
        for payload in (
            '{"status":"pending_confirmation","message":"x","transactions":[]}',
            '{"status":"needs_clarification","message":"x","transactions":[{"created_at":"2026-07-01T00:00:00Z","amount":"1","category":"Food","type":"expense"}]}',
            '{"status":"pending_confirmation","message":"x","transactions":[{"created_at":"2026-07-01T00:00:00Z","amount":"1","category":"Food","type":"income"}]}',
            '{"status":"needs_clarification","message":"x","transactions":[],"secret":"no"}',
        ):
            with self.subTest(payload=payload), self.assertRaises(ReceiptDraftLLMError):
                _parse_receipt_response(gemini_json_response(payload))
