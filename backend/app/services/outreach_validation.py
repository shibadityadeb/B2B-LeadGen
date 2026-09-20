"""Automated checks run before an outreach can be reviewed or sent to Gmail.

The important property: a failure is reported, never quietly repaired. If a
sentence asserts something no evidence supports, the draft is blocked and the
exact sentence is shown to the user.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.models.enums import ClaimKind
from app.providers.writer.base import ComposedClaim, ComposedEmail
from app.services.personalization import PersonalizationData

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Unfilled placeholders of the "[Name]" / "{{company}}" kind.
_PLACEHOLDER = re.compile(r"(\[[A-Za-z _]+\]|\{\{.*?\}\}|\{[A-Za-z_]+\}|<[A-Za-z _]+>)")

# Numbers and money amounts inside a sentence. Any figure asserted about the
# company must come from evidence, so a claim carrying one is checked against
# the excerpts it cites.
_NUMBER = re.compile(r"\b\d[\d,.]*\s*(?:%|percent|crore|lakh|million|billion|k\b|x\b)?", re.I)

# Language that makes an email read like bulk marketing.
_GENERIC_MARKETING = (
    "leading agency",
    "leading marketing agency",
    "world class",
    "world-class",
    "best in class",
    "best-in-class",
    "cutting edge",
    "cutting-edge",
    "one stop",
    "one-stop",
    "synergy",
    "revolutionary",
    "game changer",
    "game-changer",
    "unlock your potential",
    "take your business to the next level",
    "dear sir/madam",
    "dear sir or madam",
    "to whom it may concern",
    "i hope this email finds you well",
)

# Claims of a relationship or track record the system cannot substantiate.
_UNSUPPORTED_RELATIONSHIP = (
    "we have worked with",
    "we've worked with",
    "our client",
    "as your agency",
    "we helped you",
    "our work with you",
    "we partnered with you",
    "trusted by",
    "case study",
    "case studies",
    "proven results",
    "guaranteed",
    "we increased",
    "we delivered",
)

# False urgency.
_URGENCY = (
    "act now",
    "limited time",
    "last chance",
    "urgent",
    "don't miss out",
    "expires today",
    "immediately",
)


@dataclass
class ValidationIssue:
    code: str
    message: str
    #: The offending sentence, so the user sees exactly what to fix.
    context: str | None = None

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": [issue.dict() for issue in self.errors],
            "warnings": [issue.dict() for issue in self.warnings],
        }


def _digits(value: str) -> set[str]:
    """Numeric tokens, normalized so '1,200' and '1200' compare equal."""
    return {
        match.group(0).replace(",", "").replace(" ", "").rstrip(".").lower()
        for match in _NUMBER.finditer(value)
    }


def validate_outreach(
    *,
    email: ComposedEmail | None,
    claims: list[ComposedClaim],
    personalization: PersonalizationData,
    evidence_excerpts: dict[int, str],
    recipient_email: str | None,
    capability_exists: bool,
    allow_missing_recipient: bool = False,
) -> ValidationResult:
    """Check a composed draft. Errors block; warnings inform."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # --- structure ---
    if email is None or not (email.subject or "").strip():
        errors.append(ValidationIssue("missing_subject", "The email has no subject line."))
    if email is None or not (email.body or "").strip():
        errors.append(ValidationIssue("missing_body", "The email has no body."))
    if email is not None and not (email.call_to_action or "").strip():
        errors.append(
            ValidationIssue("missing_cta", "The email has no closing question or call to action.")
        )

    if email is None:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    full_text = f"{email.subject}\n{email.body}"
    lowered = full_text.lower()

    # --- recipient ---
    if not recipient_email:
        issue = ValidationIssue(
            "missing_recipient_email",
            "No recipient email address. Add one before creating a Gmail draft — "
            "an address is never derived from a person's name.",
        )
        (warnings if allow_missing_recipient else errors).append(issue)
    elif not EMAIL_PATTERN.match(recipient_email.strip()):
        errors.append(
            ValidationIssue(
                "invalid_recipient_email",
                f"'{recipient_email}' is not a valid email address.",
            )
        )

    recipient = personalization.recipient or {}
    if not recipient.get("decision_maker_id"):
        warnings.append(
            ValidationIssue(
                "no_decision_maker",
                "No decision maker is linked to this outreach.",
            )
        )
    if recipient.get("name") and recipient.get("name") not in full_text:
        # Not an error: the greeting uses the first name only.
        pass
    if not recipient.get("role") and not recipient.get("name"):
        warnings.append(
            ValidationIssue(
                "unknown_recipient",
                "Neither a name nor a role is known for the recipient.",
            )
        )

    # --- capability ---
    if not capability_exists:
        errors.append(
            ValidationIssue(
                "unknown_capability",
                "The UBM capability referenced by this outreach no longer exists.",
            )
        )

    # --- evidence binding: the central check ---
    for claim in claims:
        if not claim.requires_evidence:
            continue
        if not claim.evidence_ids:
            errors.append(
                ValidationIssue(
                    "unsupported_claim",
                    "This sentence states something about the company but cites no evidence.",
                    claim.text,
                )
            )
            continue
        missing = [
            evidence_id for evidence_id in claim.evidence_ids if evidence_id not in evidence_excerpts
        ]
        if missing:
            errors.append(
                ValidationIssue(
                    "missing_evidence",
                    f"This sentence cites evidence that no longer exists (ids: "
                    f"{', '.join(str(item) for item in missing)}).",
                    claim.text,
                )
            )
            continue

        # A figure in a claim must appear in the evidence it cites.
        claim_numbers = _digits(claim.text)
        if claim_numbers:
            supporting = " ".join(evidence_excerpts[i] for i in claim.evidence_ids)
            supported_numbers = _digits(supporting)
            invented = claim_numbers - supported_numbers
            if invented:
                errors.append(
                    ValidationIssue(
                        "fabricated_number",
                        f"This sentence contains a figure ({', '.join(sorted(invented))}) "
                        "that does not appear in the evidence it cites.",
                        claim.text,
                    )
                )

    # --- content quality ---
    for phrase in _UNSUPPORTED_RELATIONSHIP:
        if phrase in lowered:
            errors.append(
                ValidationIssue(
                    "unsupported_relationship_claim",
                    f"The text claims a relationship or track record (“{phrase}”) that the "
                    "system has no evidence for.",
                    phrase,
                )
            )
    for phrase in _GENERIC_MARKETING:
        if phrase in lowered:
            warnings.append(
                ValidationIssue(
                    "generic_marketing_language",
                    f"“{phrase}” reads like generic agency marketing.",
                    phrase,
                )
            )
    for phrase in _URGENCY:
        if phrase in lowered:
            warnings.append(
                ValidationIssue("false_urgency", f"“{phrase}” creates artificial urgency.", phrase)
            )

    placeholders = _PLACEHOLDER.findall(full_text)
    if placeholders:
        errors.append(
            ValidationIssue(
                "unfilled_placeholder",
                f"The email still contains unfilled placeholders: {', '.join(sorted(set(placeholders)))}.",
            )
        )

    if not personalization.points:
        warnings.append(
            ValidationIssue(
                "no_personalization",
                "No public observation backs this message, so it is a generic introduction.",
            )
        )

    for note in personalization.uncertainties:
        warnings.append(ValidationIssue("uncertainty", note))

    return ValidationResult(valid=not errors, errors=errors, warnings=warnings)
