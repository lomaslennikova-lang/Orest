"""Helpers for communicating with the configured LLM provider."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass(frozen=True)
class LLMConnectionStatus:
    """The result of an LLM availability check, safe to log."""

    available: bool
    message: str


def check_llm_connection(timeout: float = 10.0) -> LLMConnectionStatus:
    """Check whether the configured Gemini API key can access the API.

    The request lists available models only; it does not generate content or
    expose the API key in the returned result.
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        return LLMConnectionStatus(False, "LLM_API_KEY is not configured.")

    request_url = f"{GEMINI_MODELS_URL}?{urlencode({'key': api_key})}"
    try:
        with urlopen(request_url, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code in {401, 403}:
            return LLMConnectionStatus(False, "Gemini rejected the API key.")
        return LLMConnectionStatus(False, f"Gemini API returned HTTP {error.code}.")
    except URLError:
        return LLMConnectionStatus(False, "Could not reach the Gemini API.")
    except TimeoutError:
        return LLMConnectionStatus(False, "Timed out while connecting to the Gemini API.")
    except json.JSONDecodeError:
        return LLMConnectionStatus(False, "Gemini API returned an invalid response.")

    if payload.get("models"):
        return LLMConnectionStatus(True, "Gemini API is available.")

    return LLMConnectionStatus(False, "Gemini API returned no available models.")
