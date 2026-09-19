"""LLM providers for live agents. One provider per agent, chosen by settings.

Two wire formats:
  - Gemini REST (generateContent)
  - OpenAI-compatible chat completions (Cerebras, Groq, GitHub Models, OpenRouter, OpenAI)

Providers return text only. File changes are applied by the coordinator after validation.
"""

from typing import Any, Protocol

import httpx

from server.app.config import Settings


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured or rejects a request."""


class Provider(Protocol):
    name: str
    model: str

    async def generate(self, prompt: str) -> str: ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, base_url: str):
        if not api_key:
            raise ProviderError("GEMINI_API_KEY is not set")
        self.api_key, self.model, self.base_url = api_key, model, base_url.rstrip("/")

    async def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, params={"key": self.api_key}, json=payload)
        if response.is_error:
            raise ProviderError(f"gemini {response.status_code}: {response.text[:300]}")
        data = response.json()
        try:
            return "".join(p["text"] for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"gemini returned no text: {data}") from exc


class OpenAICompatibleProvider:
    """Cerebras, Groq, GitHub Models, OpenRouter, OpenAI: same /chat/completions shape."""

    def __init__(self, name: str, api_key: str, model: str, base_url: str):
        if not api_key:
            raise ProviderError(f"{name.upper()}_API_KEY is not set")
        self.name, self.api_key, self.model = name, api_key, model
        self.base_url = base_url.rstrip("/")

    async def generate(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.is_error:
            raise ProviderError(f"{self.name} {response.status_code}: {response.text[:300]}")
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"{self.name} returned no text: {data}") from exc


# vendor -> (default base_url, default model)
OPENAI_COMPATIBLE = {
    "cerebras": ("https://api.cerebras.ai/v1", "llama-3.3-70b"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "github": ("https://models.inference.ai.azure.com", "gpt-4o-mini"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}


def build_provider(vendor: str, settings: Settings, role: str = "") -> Provider:
    vendor = vendor.lower()
    if vendor == "gemini":
        # Per-role key (GEMINI_API_KEY_BACKEND etc.) wins; falls back to GEMINI_API_KEY.
        key = getattr(settings, f"gemini_api_key_{role}", None) or settings.gemini_api_key or ""
        return GeminiProvider(key, settings.gemini_model, settings.gemini_base_url)
    if vendor in OPENAI_COMPATIBLE:
        default_url, default_model = OPENAI_COMPATIBLE[vendor]
        key = getattr(settings, f"{vendor}_api_key", "") or ""
        model = getattr(settings, f"{vendor}_model", "") or default_model
        return OpenAICompatibleProvider(vendor, key, model, default_url)
    raise ProviderError(f"unknown provider {vendor!r}")


def build_agent_providers(settings: Settings) -> dict[str, Provider]:
    """One provider per agent role. Roles whose provider fails to build are omitted;
    the runner falls back to a scripted response for those, so one bad key never kills a run."""
    wanted = {
        "backend": settings.backend_provider,
        "frontend": settings.frontend_provider,
        "qa": settings.qa_provider,
    }
    built: dict[str, Provider] = {}
    for role, vendor in wanted.items():
        if not vendor or vendor == "none":
            continue
        try:
            built[role] = build_provider(vendor, settings, role)
        except ProviderError:
            continue
    return built
