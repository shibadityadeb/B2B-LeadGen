"""Optional LLM reasoning over evidence that has already been retrieved.

Guard rails, in order of importance:

1. The model is never asked what a company needs. It is given retrieved text
   and asked to structure it.
2. Every returned item must quote an excerpt that appears in the supplied
   text. Anything else is discarded as a fabrication — this is checked, not
   requested politely.
3. Output is parsed into Pydantic models; malformed output is dropped, never
   partially trusted.
4. Confidence never comes from the model. It is recomputed by
   ``app.services.confidence`` from the same components used for rule-based
   evidence.

If this module is skipped entirely the pipeline still produces evidence,
signals and opportunities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from app.core.logging import get_logger
from app.models.enums import EpistemicStatus, EvidenceType
from app.providers.llm.base import LLMProvider
from app.services.fingerprints import normalize_text

logger = get_logger(__name__)

VALID_EVIDENCE_TYPES = {str(item) for item in EvidenceType}

SYSTEM_PROMPT = (
    "You are an extraction tool for B2B research. You are given text that was "
    "retrieved from public web pages about one company.\n\n"
    "Rules you must follow:\n"
    "1. Only report facts stated in the supplied text.\n"
    "2. Every item must include an `excerpt` copied EXACTLY, word for word, "
    "from the supplied text. Do not paraphrase the excerpt.\n"
    "3. If the text does not support an item, do not include it.\n"
    "4. Never guess names, numbers, dates, locations or email addresses.\n"
    "5. If something is uncertain, list it under `uncertainties` instead of "
    "reporting it as a fact.\n"
    "Return only JSON."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "excerpt": {"type": "string"},
                    "evidence_type": {"type": "string"},
                    "certain": {"type": "boolean"},
                },
                "required": ["claim", "excerpt", "evidence_type"],
            },
        },
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["claims"],
}


class LLMClaim(BaseModel):
    claim: str = Field(min_length=8, max_length=400)
    excerpt: str = Field(min_length=20, max_length=1200)
    evidence_type: str
    certain: bool = True


class LLMExtraction(BaseModel):
    claims: list[LLMClaim] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class VerifiedClaim(BaseModel):
    """A model claim that survived verification against the source text."""

    claim: str
    excerpt: str
    evidence_type: str
    epistemic_status: str
    source_index: int


def _excerpt_is_present(excerpt: str, haystacks: list[str]) -> int | None:
    """Index of the source containing ``excerpt``, or None if invented.

    Compared on normalized text so whitespace and punctuation differences do
    not cause a false rejection — but the words themselves must be there.
    """
    needle = normalize_text(excerpt)
    if len(needle) < 20:
        return None
    for index, haystack in enumerate(haystacks):
        if needle in haystack:
            return index
    return None


def build_prompt(company_name: str, documents: list[tuple[str, str]]) -> str:
    """``documents`` is a list of (label, text)."""
    blocks = []
    for index, (label, text) in enumerate(documents):
        blocks.append(f"--- SOURCE {index + 1}: {label} ---\n{text}")
    joined = "\n\n".join(blocks)
    return (
        f"Company: {company_name}\n\n"
        f"Allowed evidence_type values: {', '.join(sorted(VALID_EVIDENCE_TYPES))}\n\n"
        f"Text retrieved from public pages:\n\n{joined}\n\n"
        "Extract business events and facts about this company that are stated "
        "in the text above. Copy each excerpt exactly from the text."
    )


async def extract_claims(
    provider: LLMProvider,
    *,
    company_name: str,
    documents: list[tuple[str, str]],
) -> tuple[list[VerifiedClaim], list[str], dict]:
    """Returns (verified claims, uncertainties, stats).

    ``stats`` records how many claims were rejected and why, so the run can
    report honestly on how much the model contributed.
    """
    stats = {"returned": 0, "rejected_unverified": 0, "rejected_bad_type": 0, "accepted": 0}

    if not provider.enabled or not documents:
        return [], [], stats

    raw = await provider.complete_json(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(company_name, documents),
        schema=RESPONSE_SCHEMA,
    )

    try:
        parsed = LLMExtraction.model_validate(raw)
    except ValidationError as exc:
        logger.warning("llm output failed validation: %s", exc)
        return [], [], stats

    haystacks = [normalize_text(text) for _, text in documents]
    verified: list[VerifiedClaim] = []
    stats["returned"] = len(parsed.claims)

    for claim in parsed.claims:
        evidence_type = claim.evidence_type.strip().lower()
        if evidence_type not in VALID_EVIDENCE_TYPES:
            stats["rejected_bad_type"] += 1
            continue

        source_index = _excerpt_is_present(claim.excerpt, haystacks)
        if source_index is None:
            # The model produced text that is not in the sources. Drop it.
            stats["rejected_unverified"] += 1
            continue

        verified.append(
            VerifiedClaim(
                claim=claim.claim.strip(),
                excerpt=claim.excerpt.strip(),
                evidence_type=evidence_type,
                epistemic_status=(
                    EpistemicStatus.KNOWN if claim.certain else EpistemicStatus.POSSIBLE
                ),
                source_index=source_index,
            )
        )

    stats["accepted"] = len(verified)
    if stats["rejected_unverified"]:
        logger.info(
            "dropped %s unverifiable llm claims for %s",
            stats["rejected_unverified"],
            company_name,
        )
    return verified, [item.strip() for item in parsed.uncertainties if item.strip()], stats
