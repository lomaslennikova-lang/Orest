"""Minimal Gemini REST adapter with controlled function-calling support."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.ai_chat.prompts import AI_CHAT_SYSTEM_PROMPT
from app.ai_chat.tools import FINANCIAL_TOOLS
from app.llm import GEMINI_MODELS_URL


MAX_GEMINI_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (0.5, 1.0)
RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class AIChatLLMError(RuntimeError):
    """Raised when Gemini cannot produce a usable chat turn."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class GeminiToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass(frozen=True)
class GeminiTurn:
    content: dict[str, Any]
    text: str
    tool_calls: list[GeminiToolCall]


def _function_declarations() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": _to_gemini_schema(tool.json_schema),
        }
        for tool in FINANCIAL_TOOLS.values()
    ]


def _to_gemini_schema(schema: Any) -> Any:
    """Remove JSON Schema fields unsupported by Gemini function declarations."""

    if isinstance(schema, list):
        return [_to_gemini_schema(value) for value in schema]
    if not isinstance(schema, dict):
        return schema

    return {
        key: _to_gemini_schema(value)
        for key, value in schema.items()
        if key != "additionalProperties"
    }


def _parse_turn(payload: dict[str, Any]) -> GeminiTurn:
    try:
        content = payload["candidates"][0]["content"]
        parts = content["parts"]
    except (KeyError, IndexError, TypeError) as error:
        raise AIChatLLMError("Gemini returned an unusable chat response.") from error

    text_parts: list[str] = []
    tool_calls: list[GeminiToolCall] = []
    for index, part in enumerate(parts):
        text = part.get("text")
        if isinstance(text, str):
            text_parts.append(text)

        function_call = part.get("functionCall")
        if not isinstance(function_call, dict):
            continue
        name = function_call.get("name")
        arguments = function_call.get("args", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise AIChatLLMError("Gemini returned an invalid tool call.")
        tool_calls.append(
            GeminiToolCall(name=name, arguments=arguments, call_id=f"call-{index}"),
        )

    if not text_parts and not tool_calls:
        raise AIChatLLMError("Gemini returned an empty chat response.")

    return GeminiTurn(content=content, text="\n".join(text_parts).strip(), tool_calls=tool_calls)


def _load_chat_response(request: Request, timeout: float) -> dict[str, Any]:
    """Call Gemini with a small retry budget for temporary service failures."""

    for attempt in range(MAX_GEMINI_ATTEMPTS):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as error:
            retryable = error.code in RETRYABLE_HTTP_STATUS_CODES
            if not retryable or attempt == MAX_GEMINI_ATTEMPTS - 1:
                raise AIChatLLMError(
                    "The AI service is temporarily unavailable."
                    if retryable
                    else "The AI service rejected the request.",
                    retryable=retryable,
                ) from error
        except (URLError, TimeoutError) as error:
            if attempt == MAX_GEMINI_ATTEMPTS - 1:
                raise AIChatLLMError(
                    "The AI service could not be reached.",
                    retryable=True,
                ) from error

        time.sleep(RETRY_DELAYS_SECONDS[attempt])

    raise AssertionError("The retry loop must return or raise.")


def _generate_chat_turn_sync(
    contents: list[dict[str, Any]],
    timeout: float,
) -> GeminiTurn:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise AIChatLLMError("LLM is not configured.")

    model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    request_url = f"{GEMINI_MODELS_URL}/{model}:generateContent?{urlencode({'key': api_key})}"
    request_body = json.dumps(
        {
            "systemInstruction": {"parts": [{"text": AI_CHAT_SYSTEM_PROMPT}]},
            "contents": contents,
            "tools": [{"functionDeclarations": _function_declarations()}],
            "generationConfig": {"temperature": 0.2},
        }
    ).encode()
    request = Request(
        request_url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        payload = _load_chat_response(request, timeout)
    except json.JSONDecodeError:
        raise AIChatLLMError("The AI service returned an invalid response.") from None

    return _parse_turn(payload)


async def generate_chat_turn(
    contents: list[dict[str, Any]],
    timeout: float = 30.0,
) -> GeminiTurn:
    """Call Gemini without blocking FastAPI's event loop."""

    return await asyncio.to_thread(_generate_chat_turn_sync, contents, timeout)
