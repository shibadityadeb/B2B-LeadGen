"""Deterministic evidence extraction from retrieved source text.

This is the baseline layer and it runs with no model available. It only ever
reports sentences that are actually present in the source: the excerpt is
verbatim, so a reader can open the URL and find the text.

An optional LLM layer (``app.services.llm_reasoning``) runs afterwards and
adds to this — it never replaces it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.config import settings
from app.models.enums import EpistemicStatus, EvidenceType
from app.services.evidence_taxonomy import HEDGES, PATTERNS
from app.services.fingerprints import normalize_text

# Sentence splitting that tolerates the run-on text crawlers produce.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_WHITESPACE = re.compile(r"\s+")

# Boilerplate that carries no company-specific information.
_BOILERPLATE = re.compile(
    r"\b(cookie|privacy policy|terms (of|and) (use|service|conditions)|all rights reserved|"
    r"copyright ©|subscribe to our newsletter|follow us on|sign in|log ?in|"
    r"add to cart|your cart|javascript|enable javascript)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedEvidence:
    evidence_type: EvidenceType
    claim: str
    excerpt: str
    epistemic_status: EpistemicStatus
    normalized_value: dict = field(default_factory=dict)

    @property
    def dedupe_key(self) -> str:
        return f"{self.evidence_type}:{normalize_text(self.claim)}"


def _sentences(text: str) -> list[str]:
    for raw in _SENTENCE_SPLIT.split(text or ""):
        sentence = _WHITESPACE.sub(" ", raw).strip()
        if not sentence:
            continue
        # Navigation fragments and legal boilerplate are not evidence.
        if len(sentence) < settings.research_min_excerpt_chars:
            continue
        if len(sentence) > 1200:
            continue
        if _BOILERPLATE.search(sentence):
            continue
        if sum(character.isalpha() for character in sentence) < len(sentence) * 0.5:
            continue
        yield sentence


# Numbers and places mentioned alongside a claim, kept as structured context.
_QUANTITY = re.compile(
    r"\b(\d[\d,]*)\s*(new\s+)?(stores?|showrooms?|outlets?|branches|offices?|cities|locations?|"
    r"markets?|countries|states)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(
    r"(?:(?:rs\.?|inr|usd|\$|₹)\s*\d[\d,.]*\s*(?:crore|lakh|million|billion|mn|bn)?|"
    r"\d[\d,.]*\s*(?:crore|lakh|million|billion)\b)",
    re.IGNORECASE,
)


def _normalized_value(sentence: str) -> dict:
    """Structured fragments lifted verbatim — never guessed."""
    value: dict = {}
    quantity = _QUANTITY.search(sentence)
    if quantity:
        try:
            value["quantity"] = int(quantity.group(1).replace(",", ""))
            value["unit"] = quantity.group(3).lower()
        except ValueError:
            pass
    money = _MONEY.search(sentence)
    if money:
        value["amount_text"] = money.group(0).strip()
    return value


def _truncate(sentence: str) -> str:
    limit = settings.research_max_excerpt_chars
    return sentence if len(sentence) <= limit else f"{sentence[: limit - 1]}…"


def mentions_company(text: str | None, tokens: list[str]) -> bool:
    """True when any distinctive company token appears in ``text``."""
    if not text or not tokens:
        return False
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def extract_from_text(
    text: str | None,
    *,
    company_name: str,
    max_per_type: int = 3,
    require_tokens: list[str] | None = None,
) -> list[ExtractedEvidence]:
    """Return evidence found in ``text``.

    ``max_per_type`` keeps one verbose page from flooding the profile with
    near-identical observations.

    ``require_tokens`` restricts extraction to sentences that actually name
    the company. Trade publications cover many companies in one article, and
    site furniture ("Earn by hosting sponsored links") belongs to no company
    at all — without this, a claim about a competitor would be attributed to
    the company being researched.
    """
    if not text:
        return []

    found: list[ExtractedEvidence] = []
    seen_keys: set[str] = set()
    per_type: dict[str, int] = {}

    for sentence in _sentences(text):
        # On a third-party page, only sentences naming the company can
        # support a claim about it.
        if require_tokens and not mentions_company(sentence, require_tokens):
            continue
        for pattern in PATTERNS:
            if not pattern.regex.search(sentence):
                continue

            type_key = str(pattern.evidence_type)
            if per_type.get(type_key, 0) >= max_per_type:
                break

            # A hedged sentence describes an intention, not an event.
            hedged = bool(HEDGES.search(sentence))
            status = EpistemicStatus.POSSIBLE if hedged else EpistemicStatus.KNOWN

            item = ExtractedEvidence(
                evidence_type=pattern.evidence_type,
                claim=pattern.claim.format(subject=company_name),
                excerpt=_truncate(sentence),
                epistemic_status=status,
                normalized_value=_normalized_value(sentence),
            )
            # The same claim text from two sentences on one page is one fact.
            key = f"{item.dedupe_key}:{normalize_text(sentence)[:120]}"
            if key in seen_keys:
                break
            seen_keys.add(key)

            per_type[type_key] = per_type.get(type_key, 0) + 1
            found.append(item)
            break  # first matching pattern wins for this sentence

    return found


def deduplicate(items: list[ExtractedEvidence]) -> list[ExtractedEvidence]:
    """Collapse items making the same claim, keeping the longest excerpt.

    The longest excerpt is kept because it carries the most verifiable
    context back to the source.
    """
    best: dict[str, ExtractedEvidence] = {}
    for item in items:
        current = best.get(item.dedupe_key)
        if current is None or len(item.excerpt) > len(current.excerpt):
            # Preserve the firmer epistemic status if either sighting was direct.
            if current is not None and current.epistemic_status == EpistemicStatus.KNOWN:
                item.epistemic_status = EpistemicStatus.KNOWN
            best[item.dedupe_key] = item
    return list(best.values())


# --------------------------------------------------------------------------- #
# Identity facts, extracted separately from event patterns
# --------------------------------------------------------------------------- #

_FOUNDED = re.compile(
    r"\b(?:founded|established|incorporated|set up)\s+(?:in\s+)?((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_EMPLOYEE_COUNT = re.compile(
    r"\b(\d[\d,]*)\+?\s*(?:employees|staff members|team members|people work|professionals)\b",
    re.IGNORECASE,
)


def extract_identity(
    text: str | None, *, company_name: str, require_tokens: list[str] | None = None
) -> list[ExtractedEvidence]:
    """Facts about the company itself, used for the profile and for
    contradiction detection (two sources disagreeing on headcount)."""
    if not text:
        return []

    items: list[ExtractedEvidence] = []
    for sentence in _sentences(text):
        if require_tokens and not mentions_company(sentence, require_tokens):
            continue
        founded = _FOUNDED.search(sentence)
        if founded:
            items.append(
                ExtractedEvidence(
                    evidence_type=EvidenceType.COMPANY_IDENTITY,
                    claim=f"{company_name} states a founding year of {founded.group(1)}.",
                    excerpt=_truncate(sentence),
                    epistemic_status=EpistemicStatus.KNOWN,
                    normalized_value={"attribute": "founded_year", "value": int(founded.group(1))},
                )
            )
        employees = _EMPLOYEE_COUNT.search(sentence)
        if employees:
            try:
                count = int(employees.group(1).replace(",", ""))
            except ValueError:
                continue
            items.append(
                ExtractedEvidence(
                    evidence_type=EvidenceType.COMPANY_IDENTITY,
                    claim=f"{company_name} is described as having around {count} employees.",
                    excerpt=_truncate(sentence),
                    epistemic_status=EpistemicStatus.KNOWN,
                    normalized_value={"attribute": "employee_count", "value": count},
                )
            )
    return items


def published_date_from_text(text: str | None) -> datetime | None:
    """A publication date stated in the page text itself.

    Only unambiguous formats are accepted; a wrong date is worse than none.
    """
    if not text:
        return None
    window = text[:1500]

    patterns = (
        (r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"),
        (r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", "%d %B %Y"),
        (r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b", "%B %d %Y"),
    )
    for pattern, fmt in patterns:
        match = re.search(pattern, window, re.IGNORECASE)
        if not match:
            continue
        raw = " ".join(part for part in match.groups() if part)
        if fmt == "%Y-%m-%d":
            raw = "-".join(match.groups())
        try:
            parsed = datetime.strptime(raw.title() if "%B" in fmt else raw, fmt)
        except ValueError:
            continue
        parsed = parsed.replace(tzinfo=UTC)
        # Reject nonsense: a far-future or pre-web date is a parse artefact.
        if 1990 <= parsed.year <= datetime.now(UTC).year + 1:
            return parsed
    return None
