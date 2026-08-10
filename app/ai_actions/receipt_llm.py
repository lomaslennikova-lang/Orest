"""A narrowly scoped Gemini adapter for receipt-to-draft extraction only."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.ai_actions.pending import ClarificationIssue, ExpenseTransactionDraft
from app.ai_actions.prompts import RECEIPT_DRAFT_SYSTEM_PROMPT
from app.llm import GEMINI_MODELS_URL


MAX_GEMINI_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (0.5, 1.0)
RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class ReceiptDraftLLMError(RuntimeError):
    """The receipt model did not produce a safe, usable structured result."""


class ReceiptDraftResponse(BaseModel):
    """Strict JSON contract accepted from the receipt model."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pending_confirmation", "needs_clarification"]
    message: str = Field(min_length=1, max_length=2_000)
    transactions: list[ExpenseTransactionDraft] = Field(default_factory=list, max_length=20)
    issues: list[ClarificationIssue] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ReceiptDraftResponse":
        if self.status == "pending_confirmation" and not self.transactions:
            raise ValueError("pending_confirmation requires transactions")
        if self.status == "pending_confirmation" and self.issues:
            raise ValueError("pending_confirmation must not include issues")
        if self.status == "needs_clarification" and not self.issues:
            raise ValueError("needs_clarification requires issues")
        return self


@dataclass(frozen=True)
class ReceiptDraftTurn:
    result: ReceiptDraftResponse


def _parse_receipt_response(payload: dict) -> ReceiptDraftTurn:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(part["text"] for part in parts if isinstance(part.get("text"), str))
        result_json = json.loads(text)
        return ReceiptDraftTurn(result=ReceiptDraftResponse.model_validate(result_json))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as error:
        raise ReceiptDraftLLMError("The receipt model returned an invalid draft.") from error


def _load_receipt_response(request: Request, timeout: float) -> dict:
    """Request one receipt draft with a small retry budget for transient failures."""

    for attempt in range(MAX_GEMINI_ATTEMPTS):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            retryable = error.code in RETRYABLE_HTTP_STATUS_CODES
            if not retryable or attempt == MAX_GEMINI_ATTEMPTS - 1:
                raise ReceiptDraftLLMError(
                    "The receipt AI service is temporarily unavailable."
                    if retryable
                    else "The receipt AI service rejected the request."
                ) from error
        except (URLError, TimeoutError) as error:
            if attempt == MAX_GEMINI_ATTEMPTS - 1:
                raise ReceiptDraftLLMError("The receipt AI service could not be reached.") from error

        time.sleep(RETRY_DELAYS_SECONDS[attempt])

    raise AssertionError("The retry loop must return or raise.")


def _analyse_receipt_sync(
    *,
    content: bytes,
    media_type: str,
    filename: str,
    user_message: str,
    timeout: float,
) -> ReceiptDraftTurn:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ReceiptDraftLLMError("LLM is not configured.")

    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    request_url = f"{GEMINI_MODELS_URL}/{model}:generateContent?{urlencode({'key': api_key})}"
    request_body = json.dumps(
        {
            "systemInstruction": {"parts": [{"text": RECEIPT_DRAFT_SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Проаналізуй чек. Назва файла: "
                                f"{filename}. Повідомлення користувача: {user_message}"
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": media_type,
                                "data": base64.b64encode(content).decode("ascii"),
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
    ).encode()
    request = Request(
        request_url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        payload = _load_receipt_response(request, timeout)
    except json.JSONDecodeError:
        raise ReceiptDraftLLMError("The receipt AI service returned invalid JSON.") from None

    return _parse_receipt_response(payload)


async def analyse_receipt_to_draft(
    *,
    content: bytes,
    media_type: str,
    filename: str,
    user_message: str,
    timeout: float = 30.0,
) -> ReceiptDraftTurn:
    """Send only the validated attachment and user text to Gemini, never a DB handle."""

    return await asyncio.to_thread(
        _analyse_receipt_sync,
        content=content,
        media_type=media_type,
        filename=filename,
        user_message=user_message,
        timeout=timeout,
    )
