"""LLM provider contract.

The reasoning layer is strictly optional and strictly additive. Everything in
Phase 2 — evidence, signals, opportunities, the brief — is produced without a
model; when one is configured it adds interpretation on top of evidence that
has already been retrieved and stored.

A provider is never asked an open question about a company. It is handed
retrieved text and asked to structure it, and its output is validated against
a Pydantic schema before anything is persisted.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMStatus:
    name: str
    available: bool
    model: str | None = None
    detail: str | None = None


class LLMProvider(abc.ABC):
    name: str = "base"

    @property
    @abc.abstractmethod
    def enabled(self) -> bool:
        """False for the null provider, so callers can skip the stage entirely."""

    @abc.abstractmethod
    async def complete_json(
        self, *, system: str, prompt: str, schema: dict | None = None
    ) -> dict:
        """Return parsed JSON. Implementations must raise
        :class:`app.core.errors.ProviderError` rather than returning junk."""

    @abc.abstractmethod
    async def status(self) -> LLMStatus: ...
