"""Composes an email from stored evidence, with no model involved.

This is the default writer and the reason Phase 3 runs in free mode. Every
sentence that says something about the company is assembled *from* a specific
evidence row, so traceability is structural: there is no step at which a
sentence could acquire a fact that no evidence supports.

The wording varies with tone, objective and how much evidence exists — it is
assembled, not selected from per-industry templates. Nothing here inspects
the company's industry.
"""

from __future__ import annotations

from app.models.enums import ClaimKind, MessageLength, OutreachObjective, OutreachTone
from app.providers.writer.base import (
    ComposedClaim,
    ComposedEmail,
    OutreachWriter,
    WriterContext,
)

# Openers by tone. `{observation}` is filled from an evidence-backed phrase.
_OPENERS: dict[str, tuple[str, ...]] = {
    OutreachTone.PROFESSIONAL: (
        "I came across {company}'s {observation} and it caught my attention.",
        "I noticed {company}'s {observation}.",
    ),
    OutreachTone.CONVERSATIONAL: (
        "I was reading about {company}'s {observation} the other day.",
        "I happened to see {company}'s {observation}.",
    ),
    OutreachTone.DIRECT: (
        "I saw {company}'s {observation}.",
        "Noticed {company}'s {observation}.",
    ),
    OutreachTone.WARM: (
        "I came across {company}'s {observation} and thought it was worth reaching out about.",
        "{company}'s {observation} stood out to me.",
    ),
}

_SECOND_POINT: dict[str, str] = {
    OutreachTone.PROFESSIONAL: "Their {observation} stood out too.",
    OutreachTone.CONVERSATIONAL: "Their {observation} caught my eye as well.",
    OutreachTone.DIRECT: "Their {observation} too.",
    OutreachTone.WARM: "Their {observation} stood out alongside it.",
}

_BRIDGE: dict[str, str] = {
    OutreachObjective.SHARE_IDEA: (
        "It made me think there may be something worth exploring around {capability_lower}."
    ),
    OutreachObjective.START_CONVERSATION: (
        "That is usually the point where {capability_lower} becomes worth thinking about."
    ),
    OutreachObjective.REQUEST_SHORT_CALL: (
        "It seemed like a moment where {capability_lower} might be relevant."
    ),
    OutreachObjective.EXPLORE_PARTNERSHIP: (
        "It made me wonder whether there is a partnership angle around {capability_lower}."
    ),
    OutreachObjective.INTRODUCE_CAPABILITY: (
        "We work with companies on {capability_lower}, which may or may not be relevant "
        "to what you have planned."
    ),
    OutreachObjective.RECONNECT: (
        "It felt like a reasonable moment to revisit {capability_lower}."
    ),
    OutreachObjective.FOLLOW_UP: (
        "The thought was around {capability_lower}."
    ),
}

_CALLS_TO_ACTION: dict[str, str] = {
    OutreachObjective.SHARE_IDEA: "Would it be useful if I shared the idea?",
    OutreachObjective.START_CONVERSATION: "Is this something worth a short conversation?",
    OutreachObjective.REQUEST_SHORT_CALL: "Would a short call sometime next week be useful?",
    OutreachObjective.EXPLORE_PARTNERSHIP: "Would it be worth exploring together?",
    OutreachObjective.INTRODUCE_CAPABILITY: "Happy to share more if it is relevant.",
    OutreachObjective.RECONNECT: "Would now be a better time to pick this up?",
    OutreachObjective.FOLLOW_UP: "Happy to share it if useful.",
}

_SUBJECTS: dict[str, str] = {
    OutreachObjective.SHARE_IDEA: "An idea for {company}",
    OutreachObjective.START_CONVERSATION: "{company} — {observation_short}",
    OutreachObjective.REQUEST_SHORT_CALL: "Short call about {company}'s {observation_short}?",
    OutreachObjective.EXPLORE_PARTNERSHIP: "Possible partnership around {company}'s plans",
    OutreachObjective.INTRODUCE_CAPABILITY: "{capability} for {company}",
    OutreachObjective.RECONNECT: "Reconnecting about {company}",
    OutreachObjective.FOLLOW_UP: "Following up — {previous_subject}",
}


def _greeting(name: str | None, role: str | None, tone: str) -> str:
    """Address the person if their name is published, otherwise the role.

    A generic "Dear Sir/Madam" is never produced: it signals a mail-merge,
    and inventing a name to avoid it would be worse.
    """
    if name:
        first = name.split()[0]
        if tone == OutreachTone.DIRECT:
            return f"Hi {first},"
        if tone == OutreachTone.WARM:
            return f"Hello {first},"
        return f"Hi {first},"
    if role:
        return f"Hello {role.strip()},"
    return "Hello,"


def _signature(context: WriterContext) -> str:
    if context.sender_signature:
        return context.sender_signature.strip()
    lines = ["Best,", context.sender_name]
    if context.sender_company:
        lines.append(context.sender_company)
    return "\n".join(lines)


def _shorten(observation: str) -> str:
    """A subject-line fragment: 'recent product launch' -> 'product launch'."""
    trimmed = observation.removeprefix("recent ").removeprefix("announced ")
    trimmed = trimmed.split(" or ")[0]
    return trimmed.removeprefix("a ").removeprefix("an ").strip()


class DeterministicWriter(OutreachWriter):
    name = "deterministic"

    async def generate_outreach(self, context: WriterContext) -> ComposedEmail:
        personalization = context.personalization
        strategy = context.strategy
        objective = strategy.objective
        tone = strategy.tone
        points = personalization.points

        claims: list[ComposedClaim] = []
        paragraphs: list[str] = []

        greeting = _greeting(
            personalization.recipient.get("name"),
            personalization.recipient.get("role"),
            tone,
        )

        if points:
            opener_options = _OPENERS.get(tone, _OPENERS[OutreachTone.PROFESSIONAL])
            # Deterministic variation: which opener depends on the evidence,
            # so the same inputs always produce the same email.
            opener = opener_options[points[0].evidence_ids[0] % len(opener_options)]
            first = opener.format(company=context.company_name, observation=points[0].observation)
            claims.append(
                ComposedClaim(
                    text=first,
                    kind=ClaimKind.COMPANY_FACT,
                    evidence_ids=list(points[0].evidence_ids),
                )
            )

            sentences = [first]
            # A second point only earns its place in a medium-length message.
            if len(points) > 1 and strategy.message_length == MessageLength.MEDIUM:
                second = _SECOND_POINT.get(tone, _SECOND_POINT[OutreachTone.PROFESSIONAL]).format(
                    observation=points[1].observation
                )
                claims.append(
                    ComposedClaim(
                        text=second,
                        kind=ClaimKind.COMPANY_FACT,
                        evidence_ids=list(points[1].evidence_ids),
                    )
                )
                sentences.append(second)
            paragraphs.append(" ".join(sentences))

        bridge = _BRIDGE.get(objective, _BRIDGE[OutreachObjective.START_CONVERSATION]).format(
            capability_lower=context.capability_name.lower()
        )
        claims.append(ComposedClaim(text=bridge, kind=ClaimKind.CAPABILITY_STATEMENT))
        paragraphs.append(bridge)

        if strategy.message_length == MessageLength.MEDIUM:
            about = (
                f"At {context.sender_company} we work on {context.capability_name.lower()} — "
                f"{context.capability_description[0].lower()}{context.capability_description[1:].rstrip('.')}."
            )
            claims.append(ComposedClaim(text=about, kind=ClaimKind.CAPABILITY_STATEMENT))
            paragraphs.append(about)

        call_to_action = _CALLS_TO_ACTION.get(
            objective, _CALLS_TO_ACTION[OutreachObjective.START_CONVERSATION]
        )
        claims.append(ComposedClaim(text=call_to_action, kind=ClaimKind.CALL_TO_ACTION))

        subject = self._subject(context, objective, points)
        claims.append(
            ComposedClaim(
                text=subject,
                kind=ClaimKind.COMPANY_FACT if points else ClaimKind.CAPABILITY_STATEMENT,
                evidence_ids=list(points[0].evidence_ids) if points else [],
            )
        )

        return ComposedEmail(
            subject=subject,
            greeting=greeting,
            body_paragraphs=paragraphs,
            call_to_action=call_to_action,
            signature=_signature(context),
            claims=claims,
            generated_by=self.name,
        )

    def _subject(self, context: WriterContext, objective: str, points: list) -> str:
        template = _SUBJECTS.get(objective, _SUBJECTS[OutreachObjective.START_CONVERSATION])
        observation_short = _shorten(points[0].observation) if points else ""
        subject = template.format(
            company=context.company_name,
            observation_short=observation_short,
            capability=context.capability_name,
            previous_subject=context.previous_subject or context.company_name,
        )
        # With no observation the "{company} — " form would trail an em dash.
        return subject.replace(" — ", " ").strip(" —-") if not points else subject

    async def generate_follow_up(self, context: WriterContext) -> ComposedEmail:
        """Shorter than the first message, and it does not repeat it."""
        personalization = context.personalization
        points = personalization.points
        claims: list[ComposedClaim] = []

        greeting = _greeting(
            personalization.recipient.get("name"),
            personalization.recipient.get("role"),
            context.strategy.tone,
        )

        # "about recent product launch" needs a determiner; the capability
        # name does not take one.
        topic = (
            f"their {points[0].observation}"
            if points
            else context.capability_name.lower()
        )
        opening = f"Just following up on my earlier note about {topic}."
        claims.append(
            ComposedClaim(
                text=opening,
                kind=ClaimKind.COMPANY_FACT if points else ClaimKind.CAPABILITY_STATEMENT,
                evidence_ids=list(points[0].evidence_ids) if points else [],
            )
        )

        bridge = (
            f"The thought was around {context.capability_name.lower()}, in case it is "
            "relevant to what you have planned."
        )
        claims.append(ComposedClaim(text=bridge, kind=ClaimKind.CAPABILITY_STATEMENT))

        call_to_action = "Happy to share the idea if it is useful — and equally happy to leave it if not."
        claims.append(ComposedClaim(text=call_to_action, kind=ClaimKind.CALL_TO_ACTION))

        subject = (
            f"Following up — {context.previous_subject}"
            if context.previous_subject
            else f"Following up — {context.company_name}"
        )
        claims.append(ComposedClaim(text=subject, kind=ClaimKind.CAPABILITY_STATEMENT))

        return ComposedEmail(
            subject=subject,
            greeting=greeting,
            body_paragraphs=[opening, bridge],
            call_to_action=call_to_action,
            signature=_signature(context),
            claims=claims,
            generated_by=self.name,
        )
