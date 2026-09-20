"""Chooses the communication structure before any words are written.

The strategy is a small structured object, not model narration: it records
*what* the message will do, so the reviewer can see the plan without being
shown any internal reasoning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.models import UbmCapability
from app.models.enums import MessageLength, OutreachObjective, OutreachTone
from app.services.personalization import PersonalizationData


@dataclass
class OutreachStrategy:
    objective: str
    primary_signal: str | None
    relevant_capability: str
    recipient_role: str | None
    personalization_points: list[str] = field(default_factory=list)
    call_to_action: str = ""
    tone: str = OutreachTone.PROFESSIONAL
    message_length: str = MessageLength.SHORT
    notes: list[str] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


# Each objective's closing ask. Low-pressure by design: the message asks
# permission to share something, it does not push for a meeting.
_CALLS_TO_ACTION: dict[str, str] = {
    OutreachObjective.START_CONVERSATION: "ask whether the topic is worth a short conversation",
    OutreachObjective.SHARE_IDEA: "offer to share the idea if it is useful",
    OutreachObjective.REQUEST_SHORT_CALL: "ask for a short call if the timing suits",
    OutreachObjective.EXPLORE_PARTNERSHIP: "ask whether a partnership conversation is of interest",
    OutreachObjective.INTRODUCE_CAPABILITY: "offer relevant context on the capability",
    OutreachObjective.FOLLOW_UP: "check whether the earlier note is worth picking up",
    OutreachObjective.RECONNECT: "ask whether it is a better time to reconnect",
}


def choose_objective(
    personalization: PersonalizationData,
    *,
    is_follow_up: bool = False,
    requested: str | None = None,
) -> OutreachObjective:
    """Pick an objective the evidence can actually support.

    With no concrete observation the message cannot credibly "share an idea"
    about a specific initiative, so it falls back to a plain introduction.
    """
    if is_follow_up:
        return OutreachObjective.FOLLOW_UP
    if requested:
        return OutreachObjective(requested)
    if not personalization.points:
        return OutreachObjective.INTRODUCE_CAPABILITY
    if len(personalization.points) >= 2:
        return OutreachObjective.SHARE_IDEA
    return OutreachObjective.START_CONVERSATION


def build_strategy(
    *,
    personalization: PersonalizationData,
    capability: UbmCapability,
    tone: str = OutreachTone.PROFESSIONAL,
    message_length: str = MessageLength.SHORT,
    is_follow_up: bool = False,
    requested_objective: str | None = None,
) -> OutreachStrategy:
    objective = choose_objective(
        personalization, is_follow_up=is_follow_up, requested=requested_objective
    )

    notes: list[str] = []
    if not personalization.points:
        notes.append(
            "No public observation was available, so the message introduces the capability "
            "without claiming anything specific about the company."
        )
    if not personalization.recipient.get("name"):
        notes.append("The greeting addresses the role, because no name is published.")

    return OutreachStrategy(
        objective=str(objective),
        primary_signal=(
            personalization.business_signal["title"]
            if personalization.business_signal
            else None
        ),
        relevant_capability=capability.name,
        recipient_role=personalization.recipient.get("role"),
        personalization_points=[point.observation for point in personalization.points],
        call_to_action=_CALLS_TO_ACTION[objective],
        tone=str(tone),
        message_length=str(message_length),
        notes=notes,
    )
