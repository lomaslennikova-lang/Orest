from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import ValidationError

from app.ai_actions.pending import ExpenseActionDraft
from app.ai_actions.transactions import (
    TransactionCreateData,
    TransactionValidationError,
    normalise_transaction_data,
)


class PendingActionSchemaTests(unittest.TestCase):
    def test_draft_accepts_only_expense_and_serialises_snapshot(self):
        draft = ExpenseActionDraft.model_validate(
            {
                "transactions": [
                    {
                        "created_at": "2026-07-01T12:00:00Z",
                        "amount": "12.50",
                        "category": " Food ",
                        "type": "expense",
                    }
                ]
            }
        )

        snapshot = draft.model_dump(mode="json")
        self.assertEqual(snapshot["transactions"][0]["type"], "expense")
        self.assertEqual(snapshot["transactions"][0]["category"], "Food")

    def test_draft_rejects_income_and_unknown_fields(self):
        with self.assertRaises(ValidationError):
            ExpenseActionDraft.model_validate(
                {
                    "transactions": [
                        {
                            "created_at": "2026-07-01T12:00:00Z",
                            "amount": "12.50",
                            "category": "Food",
                            "type": "income",
                        }
                    ]
                }
            )
        with self.assertRaises(ValidationError):
            ExpenseActionDraft.model_validate(
                {
                    "transactions": [
                        {
                            "created_at": "2026-07-01T12:00:00Z",
                            "amount": "12.50",
                            "category": "Food",
                            "unexpected": True,
                        }
                    ]
                }
            )

    def test_shared_transaction_rules_normalise_and_reject_future_dates(self):
        normalised = normalise_transaction_data(
            TransactionCreateData(
                created_at=datetime(2026, 7, 1, 12, tzinfo=timezone.utc),
                amount=Decimal("12.505"),
                category=" Food ",
                transaction_type="expense",
            )
        )
        self.assertEqual(normalised.amount, Decimal("12.50"))
        self.assertEqual(normalised.category, "food")

        with self.assertRaises(TransactionValidationError):
            normalise_transaction_data(
                TransactionCreateData(
                    created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
                    amount=Decimal("12.50"),
                    category="Food",
                    transaction_type="expense",
                )
            )
