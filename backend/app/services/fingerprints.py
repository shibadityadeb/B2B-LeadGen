"""Stable hashes used for idempotency across research runs.

A fingerprint answers "have we seen this exact observation before?". It must
be stable across runs and insensitive to incidental text differences, so
repeated research updates a row rather than inserting a near-duplicate.
"""

from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]")


def normalize_text(value: str | None) -> str:
    """Lowercase, strip punctuation and collapse whitespace."""
    if not value:
        return ""
    text = _PUNCTUATION.sub(" ", value.lower())
    return _WHITESPACE.sub(" ", text).strip()


def sha256(*parts: str | None) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update((part or "").encode("utf-8"))
        digest.update(b"\x1f")  # unit separator: avoids field-boundary collisions
    return digest.hexdigest()


def content_hash(content: str | None) -> str | None:
    """Hash of page content, used to skip unchanged pages on a re-run."""
    if not content:
        return None
    return hashlib.sha256(normalize_text(content).encode("utf-8")).hexdigest()


def evidence_fingerprint(company_id: int, evidence_type: str, claim: str) -> str:
    return sha256(str(company_id), evidence_type, normalize_text(claim))


def signal_fingerprint(company_id: int, signal_type: str) -> str:
    """One signal row per (company, type): a re-run updates it in place."""
    return sha256(str(company_id), signal_type)


def opportunity_fingerprint(company_id: int, capability_id: int) -> str:
    return sha256(str(company_id), "capability", str(capability_id))


def decision_maker_fingerprint(company_id: int, name: str | None, role: str) -> str:
    """Role-only records stay distinct from named ones."""
    return sha256(str(company_id), normalize_text(name) or "__unknown__", normalize_text(role))
