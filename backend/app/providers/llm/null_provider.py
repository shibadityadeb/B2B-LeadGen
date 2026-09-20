"""The default: no model configured.

Its presence means the rest of the code never needs an `if llm is not None`
branch — the orchestrator checks ``enabled`` once and skips the stage.
"""

from __future__ import annotations

from app.providers.llm.base import LLMProvider, LLMStatus


class NullLLMProvider(LLMProvider):
    name = "none"

    @property
    def enabled(self) -> bool:
        return False

    async def complete_json(self, *, system: str, prompt: str, schema: dict | None = None) -> dict:
        raise RuntimeError("No LLM provider is configured.")

    async def status(self) -> LLMStatus:
        return LLMStatus(
            self.name,
            False,
            None,
            "No LLM configured. Research runs use deterministic extraction only.",
        )
