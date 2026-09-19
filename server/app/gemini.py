"""Minimal server-side Gemini provider.

This module uses Gemini's REST API directly so the UI never sees the API key and
no additional SDK is required. It intentionally returns text only; file changes
must be applied by the coordinator after validation.
"""

from typing import Any

import httpx

from server.app.config import Settings


class GeminiConfigurationError(RuntimeError):
    """Raised when live Gemini mode is not configured."""


class GeminiError(RuntimeError):
    """Raised when Gemini rejects a request."""


class GeminiProvider:
    def __init__(self, settings: Settings, api_key: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise GeminiConfigurationError(
                "Set GEMINI_API_KEY in .env before starting live agent mode."
            )
        self.settings = settings

    async def generate(self, prompt: str) -> str:
        url = (
            f"{self.settings.gemini_base_url.rstrip('/')}/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json=payload,
            )
        if response.is_error:
            raise GeminiError(
                f"Gemini request failed ({response.status_code}): {response.text[:500]}"
            )
        data = response.json()
        try:
            return "".join(part["text"] for part in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiError(f"Gemini returned no text: {data}") from exc
