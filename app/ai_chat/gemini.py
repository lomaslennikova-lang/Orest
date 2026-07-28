"""Minimal Gemini REST adapter with controlled function-calling support."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.ai_chat.prompts import AI_CHAT_SYSTEM_PROMPT
from app.ai_chat.tools import FINANCIAL_TOOLS
from app.llm import GEMINI_MODELS_URL


class AIChatLLMError(Exception):
    """Raised when Gemini cannot produce a usable chat turn."""


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
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise AIChatLLMError("The AI service is temporarily unavailable.") from error
    except (URLError, TimeoutError):
        raise AIChatLLMError("The AI service could not be reached.") from None
    except json.JSONDecodeError:
        raise AIChatLLMError("The AI service returned an invalid response.") from None

    return _parse_turn(payload)


async def generate_chat_turn(
    contents: list[dict[str, Any]],
    timeout: float = 30.0,
) -> GeminiTurn:
    """Call Gemini without blocking FastAPI's event loop."""

    return await asyncio.to_thread(_generate_chat_turn_sync, contents, timeout)
