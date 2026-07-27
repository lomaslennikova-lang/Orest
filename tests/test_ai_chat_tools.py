from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from app.ai_chat.schemas import (
    CategoryTotalsParams,
    PeriodComparisonParams,
    TransactionsSummaryParams,
)
from app.ai_chat.tools import (
    FINANCIAL_TOOLS,
    get_category_totals,
    get_period_comparison,
    get_transactions_summary,
)


class FakeResult:
    def __init__(self, *, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def one(self):
        return self._one

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, results):
        self.results = iter(results)

    async def execute(self, _statement):
        return next(self.results)


class FinancialToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_serializes_only_aggregates(self):
        row = SimpleNamespace(
            transactions_count=3,
            total_income=Decimal("1000.00"),
            total_expense=Decimal("250.50"),
            period_from=date(2026, 6, 1),
            period_to=date(2026, 6, 30),
        )

        result = await get_transactions_summary(
            FakeSession([FakeResult(one=row)]),
            TransactionsSummaryParams(date_from=date(2026, 6, 1), date_to=date(2026, 6, 30)),
        )

        self.assertEqual(result["transactions_count"], 3)
        self.assertEqual(result["total_income"], 1000.0)
        self.assertEqual(result["total_expense"], 250.5)
        self.assertEqual(result["balance"], 749.5)
        self.assertNotIn("transactions", result)

    async def test_category_tool_returns_minimal_category_rows(self):
        rows = [
            SimpleNamespace(category="Продукти", amount=Decimal("400"), transactions_count=4),
            SimpleNamespace(category="Транспорт", amount=Decimal("120"), transactions_count=2),
        ]

        result = await get_category_totals(
            FakeSession([FakeResult(rows=rows)]),
            CategoryTotalsParams(limit=10),
        )

        self.assertEqual(result["categories"][0]["category"], "Продукти")
        self.assertEqual(result["categories"][0]["amount"], 400.0)
        self.assertNotIn("user", result["categories"][0])

    async def test_period_comparison_calculates_differences(self):
        current = SimpleNamespace(
            transactions_count=2,
            total_income=Decimal("500"),
            total_expense=Decimal("300"),
            period_from=date(2026, 6, 1),
            period_to=date(2026, 6, 30),
        )
        previous = SimpleNamespace(
            transactions_count=2,
            total_income=Decimal("400"),
            total_expense=Decimal("350"),
            period_from=date(2026, 5, 1),
            period_to=date(2026, 5, 31),
        )

        result = await get_period_comparison(
            FakeSession([FakeResult(one=current), FakeResult(one=previous)]),
            PeriodComparisonParams(
                current_from=date(2026, 6, 1),
                current_to=date(2026, 6, 30),
                previous_from=date(2026, 5, 1),
                previous_to=date(2026, 5, 31),
            ),
        )

        self.assertEqual(result["difference"], {
            "total_income": 100.0,
            "total_expense": -50.0,
            "balance": 150.0,
        })


class ToolContractTests(unittest.TestCase):
    def test_registry_exposes_only_planned_read_only_tools(self):
        self.assertEqual(
            set(FINANCIAL_TOOLS),
            {
                "get_transactions_summary",
                "get_category_totals",
                "get_top_expenses",
                "get_period_comparison",
                "get_daily_expenses",
            },
        )

    def test_invalid_period_is_rejected_before_database_access(self):
        with self.assertRaises(ValidationError):
            TransactionsSummaryParams(
                date_from=date(2026, 7, 2),
                date_to=date(2026, 7, 1),
            )

    def test_overlapping_comparison_periods_are_rejected(self):
        with self.assertRaises(ValidationError):
            PeriodComparisonParams(
                current_from=date(2026, 6, 1),
                current_to=date(2026, 6, 30),
                previous_from=date(2026, 5, 15),
                previous_to=date(2026, 6, 1),
            )
