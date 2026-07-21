"""Prompt templates used for LLM requests."""

from __future__ import annotations

import json
from typing import Any


FINANCIAL_ANALYSIS_PROMPT = """Ти — фінансовий помічник. Проаналізуй передані
агреговані дані транзакцій у гривнях. Не вигадуй фактів, яких немає в даних.
Пиши українською, зрозуміло, стисло й доброзичливо. Це інформаційний огляд, а
не професійна фінансова порада.

Поверни лише коректний JSON-об'єкт без Markdown і без додаткового тексту з
такими полями:
- summary: короткий загальний висновок про стан фінансів і витрати;
- top_expense_categories: масив до 5 рядків з категоріями найбільших витрат;
- risks: масив можливих фінансових ризиків (або порожній масив, якщо їх немає);
- advice: масив рівно з трьох практичних порад щодо оптимального використання
  наявних коштів.

Дані для аналізу:
{transactions_json}
"""


def build_financial_analysis_prompt(financial_data: dict[str, Any]) -> str:
    """Build the reusable financial-analysis prompt with safe JSON data."""
    transactions_json = json.dumps(financial_data, ensure_ascii=False)
    return FINANCIAL_ANALYSIS_PROMPT.format(transactions_json=transactions_json)
