"""Legal transitions for an outreach.

Centralised so an impossible move — draft straight to sent, or sending
something that was never approved — is refused in one place rather than
being prevented by luck in each endpoint.
"""

from __future__ import annotations

from app.core.errors import ConflictError
from app.models.enums import OutreachStatus

# from -> allowed next states
TRANSITIONS: dict[str, set[str]] = {
    OutreachStatus.DRAFT: {
        OutreachStatus.REVIEW,
        OutreachStatus.DRAFT,          # regeneration keeps it a draft
        OutreachStatus.CANCELLED,
    },
    OutreachStatus.REVIEW: {
        OutreachStatus.APPROVED,
        OutreachStatus.REJECTED,
        OutreachStatus.DRAFT,          # editing sends it back for rework
        OutreachStatus.REVIEW,
        OutreachStatus.CANCELLED,
    },
    OutreachStatus.APPROVED: {
        OutreachStatus.GMAIL_DRAFT_CREATED,
        OutreachStatus.REVIEW,         # an edit after approval needs re-review
        # A reviewer must always be able to change their mind before it goes.
        OutreachStatus.REJECTED,
        OutreachStatus.APPROVED,
        OutreachStatus.CANCELLED,
    },
    OutreachStatus.GMAIL_DRAFT_CREATED: {
        # The human sends from Gmail and marks it here.
        OutreachStatus.SENT,
        OutreachStatus.GMAIL_DRAFT_CREATED,
        OutreachStatus.REVIEW,
        OutreachStatus.REJECTED,
        OutreachStatus.CANCELLED,
    },
    OutreachStatus.SENT: {
        OutreachStatus.FOLLOW_UP_DUE,
        OutreachStatus.COMPLETED,
        OutreachStatus.SENT,
    },
    OutreachStatus.FOLLOW_UP_DUE: {
        OutreachStatus.COMPLETED,
        OutreachStatus.SENT,
        OutreachStatus.FOLLOW_UP_DUE,
    },
    OutreachStatus.COMPLETED: {OutreachStatus.COMPLETED},
    OutreachStatus.CANCELLED: {OutreachStatus.CANCELLED},
    OutreachStatus.REJECTED: {
        OutreachStatus.DRAFT,          # rework after a rejection
        OutreachStatus.REVIEW,
        OutreachStatus.CANCELLED,
        OutreachStatus.REJECTED,
    },
}

#: Statuses from which a Gmail draft may be created. Approval is mandatory:
#: this is the phase's central safety rule.
CAN_CREATE_GMAIL_DRAFT = {OutreachStatus.APPROVED, OutreachStatus.GMAIL_DRAFT_CREATED}

#: Statuses from which an outreach may be marked as sent by a human.
#: Approved-without-a-Gmail-draft is allowed on purpose: a user may send the
#: message from any client. What is *not* allowed is marking an unreviewed
#: draft as sent.
CAN_MARK_SENT = {OutreachStatus.GMAIL_DRAFT_CREATED, OutreachStatus.APPROVED}


def can_transition(current: str, target: str) -> bool:
    return str(target) in {str(item) for item in TRANSITIONS.get(str(current), set())}


def ensure_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise ConflictError(
            f"An outreach cannot move from '{current}' to '{target}'.",
            details={"current": str(current), "requested": str(target)},
        )


def ensure_can_create_gmail_draft(current: str) -> None:
    if str(current) not in {str(item) for item in CAN_CREATE_GMAIL_DRAFT}:
        raise ConflictError(
            "This outreach must be approved before a Gmail draft can be created.",
            details={"current": str(current)},
        )


def ensure_can_mark_sent(current: str) -> None:
    if str(current) not in {str(item) for item in CAN_MARK_SENT}:
        raise ConflictError(
            "This outreach must be approved before it can be marked as sent.",
            details={"current": str(current)},
        )
