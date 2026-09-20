"""Ollama-backed reasoning layer (local, free, no API key)."""

from __future__ import annotations

import json

import httpx

from app.core.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers.llm.base import LLMProvider, LLMStatus

logger = get_logger(__name__)


class OllamaLLMProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or settings.llm_model
        self.base_url = (base_url or settings.ollama_url).rstrip("/")

    @property
    def enabled(self) -> bool:
        return True

    async def complete_json(self, *, system: str, prompt: str, schema: dict | None = None) -> dict:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            # Ollama's structured-output mode: the model is constrained to the
            # schema, which removes most parse failures.
            "format": schema or "json",
            "options": {
                # Deterministic-ish: this is an extraction task, not creative work.
                "temperature": 0.1,
                "num_ctx": 8192,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"Could not reach Ollama at {self.base_url}: {exc}",
                details={"provider": self.name},
            ) from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Ollama returned HTTP {response.status_code}: {response.text[:200]}",
                details={"provider": self.name},
            )

        body = response.json().get("response", "")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"Ollama did not return valid JSON: {body[:200]}",
                details={"provider": self.name},
            ) from exc

        if not isinstance(parsed, dict):
            raise ProviderError(
                "Ollama returned JSON that is not an object.",
                details={"provider": self.name},
            )
        return parsed

    async def status(self) -> LLMStatus:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                return LLMStatus(self.name, False, self.model, f"HTTP {response.status_code}")
            models = [item.get("name", "") for item in response.json().get("models", [])]
            # Ollama reports "llama3.1:8b"; a bare "llama3.1" should still match.
            if any(name == self.model or name.startswith(f"{self.model}:") for name in models):
                return LLMStatus(self.name, True, self.model, f"Model '{self.model}' is available.")
            return LLMStatus(
                self.name,
                False,
                self.model,
                f"Ollama is running but '{self.model}' is not pulled. Run: ollama pull {self.model}",
            )
        except httpx.HTTPError as exc:
            return LLMStatus(self.name, False, self.model, f"Not reachable: {exc}")
