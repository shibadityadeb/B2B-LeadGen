from __future__ import annotations

from app.core.config import settings
from app.core.errors import AppError
from app.providers.llm.base import LLMProvider
from app.providers.llm.null_provider import NullLLMProvider
from app.providers.llm.ollama_provider import OllamaLLMProvider

_BUILDERS: dict[str, type[LLMProvider]] = {
    "none": NullLLMProvider,
    "ollama": OllamaLLMProvider,
}


def available_providers() -> list[str]:
    return sorted(_BUILDERS)


def get_llm_provider(name: str | None = None) -> LLMProvider:
    key = (name or settings.llm_provider or "none").lower().strip()
    builder = _BUILDERS.get(key)
    if builder is None:
        raise AppError(
            f"Unknown LLM provider '{key}'. Available: {', '.join(available_providers())}."
        )
    return builder()
