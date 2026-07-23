"""Prompt templates used for LLM requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FINANCIAL_ANALYSIS_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "promts" / "financial_analysis_gemini.md"
)


def _load_financial_analysis_prompt() -> str:
    """Load the editable Gemini financial-analysis prompt template."""
    return FINANCIAL_ANALYSIS_PROMPT_PATH.read_text(encoding="utf-8")


def build_financial_analysis_prompt(financial_data: dict[str, Any]) -> str:
    """Build the reusable financial-analysis prompt with safe JSON data."""
    transactions_json = json.dumps(financial_data, ensure_ascii=False)
    return _load_financial_analysis_prompt().format(transactions_json=transactions_json)
