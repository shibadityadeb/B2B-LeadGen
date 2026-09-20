"""Outreach orchestration.

Boundaries this service enforces:

* Generation never invents: it composes from Phase 2 evidence, and the result
  is validated before it can be reviewed.
* Regeneration adds a version; nothing is destroyed, and a user's own edits
  are never silently overwritten.
* A Gmail draft requires prior human approval and a clean validation.
* Nothing here can send an email — the delivery interface has no send method.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models import (
    Company,
    DecisionMaker,
    Evidence,
    Opportunity,
    Outreach,
    OutreachClaim,
    OutreachClaimEvidence,
    OutreachOutcome,
    OutreachVersion,
    SenderProfile,
    Signal,
    UbmCapability,
)
from app.models.enums import (
    AuditAction,
    GenerationMethod,
    MessageLength,
    OutcomeStatus,
    OutreachStatus,
    OutreachTone,
)
from app.providers.outreach.base import DraftMessage, OutreachDeliveryProvider
from app.providers.outreach.registry import get_delivery_provider
from app.providers.writer.base import (
    ComposedClaim,
    ComposedEmail,
    OutreachWriter,
    WriterContext,
)
from app.providers.writer.deterministic import DeterministicWriter
from app.repositories.outreach import (
    OutreachRepository,
    OutreachVersionRepository,
    SenderProfileRepository,
)
from app.repositories.research import (
    CapabilityRepository,
    DecisionMakerRepository,
    EvidenceRepository,
    OpportunityRepository,
    SignalRepository,
)
from app.services import audit
from app.services import outreach_state
from app.services.outreach_strategy import build_strategy
from app.services.outreach_validation import (
    ValidationIssue,
    ValidationResult,
    validate_outreach,
)
from app.services.personalization import (
    PersonalizationData,
    PersonalizationPoint,
    build_personalization,
    email_display_name,
)

logger = get_logger(__name__)

DEFAULT_SENDER = {
    "name": "UBM Team",
    "role": "Business Development",
    "company": "Upshot Brand Media",
    "website": "https://www.upshotbrandmedia.com/",
}


class OutreachService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        writer: OutreachWriter | None = None,
        delivery: OutreachDeliveryProvider | None = None,
    ):
        self.session = session
        self.outreach = OutreachRepository(session)
        self.versions = OutreachVersionRepository(session)
        self.senders = SenderProfileRepository(session)
        self.opportunities = OpportunityRepository(session)
        self.capabilities = CapabilityRepository(session)
        self.evidence = EvidenceRepository(session)
        self.signals = SignalRepository(session)
        self.people = DecisionMakerRepository(session)
        self._writer = writer
        self._delivery = delivery

    @property
    def writer(self) -> OutreachWriter:
        # The deterministic writer is the default so Phase 3 runs with no
        # model configured; an LLM writer is injected by the caller.
        if self._writer is None:
            self._writer = DeterministicWriter()
        return self._writer

    async def delivery(self) -> OutreachDeliveryProvider:
        if self._delivery is None:
            self._delivery = await get_delivery_provider(self.session)
        return self._delivery

    # ------------------------------------------------------------------ #
    # sender profile
    # ------------------------------------------------------------------ #

    async def ensure_sender_profile(self) -> SenderProfile:
        """Return the configured sender, creating a neutral placeholder once.

        The placeholder carries no real person's details — it exists so the
        UI has something to show until the user fills it in.
        """
        profile = await self.senders.get_default()
        if profile is None:
            profile = await self.senders.create(**DEFAULT_SENDER, is_default=True)
            await self.session.commit()
        return profile

    # ------------------------------------------------------------------ #
    # creation and generation
    # ------------------------------------------------------------------ #

    async def _load_context(
        self, opportunity: Opportunity, decision_maker: DecisionMaker | None
    ) -> tuple[Company, UbmCapability, list[Evidence], list[Signal]]:
        company = await self.session.get(Company, opportunity.company_id)
        if company is None:
            raise NotFoundError(f"Company {opportunity.company_id} not found")

        capability = await self.capabilities.get(opportunity.capability_id)
        if capability is None:
            raise NotFoundError("The UBM capability for this opportunity no longer exists")

        # Only the evidence this opportunity actually rests on.
        evidence_ids = [link.evidence_id for link in opportunity.evidence_links]
        evidence: list[Evidence] = []
        if evidence_ids:
            rows = await self.session.scalars(
                select(Evidence)
                .where(Evidence.id.in_(evidence_ids))
                # The source is needed for provenance display and reliability.
                .options(selectinload(Evidence.source))
            )
            evidence = list(rows)

        signal_ids = [link.signal_id for link in opportunity.signal_links]
        signals: list[Signal] = []
        if signal_ids:
            rows = await self.session.scalars(
                select(Signal)
                .where(Signal.id.in_(signal_ids))
                .options(selectinload(Signal.evidence_links))
            )
            signals = list(rows)

        return company, capability, evidence, signals

    async def create_from_opportunity(
        self,
        *,
        opportunity_id: int,
        decision_maker_id: int | None = None,
        campaign_id: int | None = None,
        tone: str = OutreachTone.PROFESSIONAL,
        message_length: str = MessageLength.SHORT,
        objective: str | None = None,
        actor: str | None = None,
        reuse_existing: bool = True,
    ) -> Outreach:
        """Prepare an outreach for review. Nothing is sent, and no Gmail draft
        is created at this point."""
        opportunity = await self.session.get(Opportunity, opportunity_id)
        if opportunity is None:
            raise NotFoundError(f"Opportunity {opportunity_id} not found")
        await self.session.refresh(opportunity, ["evidence_links", "signal_links"])

        if reuse_existing:
            existing = await self.outreach.existing_for(
                opportunity_id=opportunity_id, decision_maker_id=decision_maker_id
            )
            if existing is not None:
                return existing

        decision_maker = None
        if decision_maker_id is not None:
            decision_maker = await self.session.get(DecisionMaker, decision_maker_id)
            if decision_maker is None:
                raise NotFoundError(f"Decision maker {decision_maker_id} not found")
            await self.session.refresh(decision_maker, ["source"])
        else:
            # Prefer a marketing-side contact whose name is actually published.
            candidates = await self.people.list_for_company(opportunity.company_id)
            named = [person for person in candidates if person.name]
            preferred = [
                person for person in named if person.role_category in ("marketing", "founder")
            ]
            decision_maker = (preferred or named or candidates or [None])[0]

        sender = await self.ensure_sender_profile()
        company, capability, evidence, signals = await self._load_context(
            opportunity, decision_maker
        )

        outreach = await self.outreach.create(
            company_id=company.id,
            opportunity_id=opportunity.id,
            decision_maker_id=decision_maker.id if decision_maker else None,
            campaign_id=campaign_id,
            sender_profile_id=sender.id,
            status=OutreachStatus.DRAFT,
            tone=str(tone),
            message_length=str(message_length),
            to_email=decision_maker.email if decision_maker else None,
            to_name=decision_maker.name if decision_maker else None,
            owner=sender.name,
        )
        await self.session.flush()

        await audit.record(
            self.session,
            action=AuditAction.OUTREACH_CREATED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor or sender.name,
            detail={"opportunity_id": opportunity.id, "company_id": company.id},
        )

        await self._generate(
            outreach,
            opportunity=opportunity,
            company=company,
            capability=capability,
            evidence=evidence,
            signals=signals,
            decision_maker=decision_maker,
            sender=sender,
            method=GenerationMethod.AI
            if self.writer.name != "deterministic"
            else GenerationMethod.DETERMINISTIC,
            objective=objective,
            actor=actor,
        )
        await self.session.commit()
        return outreach

    async def regenerate(
        self, outreach_id: int, *, tone: str | None = None,
        message_length: str | None = None, objective: str | None = None,
        actor: str | None = None,
    ) -> Outreach:
        """Produce a new version. The previous ones remain available."""
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")
        if outreach.status in (OutreachStatus.SENT, OutreachStatus.COMPLETED):
            raise ConflictError("An outreach that has been sent cannot be regenerated.")

        if tone:
            outreach.tone = str(tone)
        if message_length:
            outreach.message_length = str(message_length)

        opportunity = await self.session.get(Opportunity, outreach.opportunity_id)
        if opportunity is None:
            raise NotFoundError("The opportunity behind this outreach no longer exists")
        await self.session.refresh(opportunity, ["evidence_links", "signal_links"])

        decision_maker = (
            await self.session.get(DecisionMaker, outreach.decision_maker_id)
            if outreach.decision_maker_id
            else None
        )
        if decision_maker:
            await self.session.refresh(decision_maker, ["source"])

        sender = (
            await self.senders.get(outreach.sender_profile_id)
            if outreach.sender_profile_id
            else None
        ) or await self.ensure_sender_profile()

        company, capability, evidence, signals = await self._load_context(
            opportunity, decision_maker
        )

        # Regenerating a follow-up must produce a follow-up, not a fresh
        # first-contact email.
        is_follow_up = outreach.follow_up_number > 0
        parent = (
            await self.outreach.get(outreach.parent_outreach_id)
            if outreach.parent_outreach_id
            else None
        )

        await self._generate(
            outreach,
            opportunity=opportunity,
            company=company,
            capability=capability,
            evidence=evidence,
            signals=signals,
            decision_maker=decision_maker,
            sender=sender,
            method=GenerationMethod.REGENERATED,
            objective=objective,
            actor=actor,
            is_follow_up=is_follow_up,
            previous=parent,
        )
        # A regenerated message has not been reviewed.
        if outreach.status in (OutreachStatus.APPROVED, OutreachStatus.REVIEW):
            outreach.status = OutreachStatus.REVIEW
            outreach.approved_at = None

        await audit.record(
            self.session,
            action=AuditAction.EMAIL_REGENERATED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
        )
        await self.session.commit()
        return outreach

    async def _generate(
        self,
        outreach: Outreach,
        *,
        opportunity: Opportunity,
        company: Company,
        capability: UbmCapability,
        evidence: list[Evidence],
        signals: list[Signal],
        decision_maker: DecisionMaker | None,
        sender: SenderProfile,
        method: str,
        objective: str | None,
        actor: str | None,
        is_follow_up: bool = False,
        previous: Outreach | None = None,
    ) -> OutreachVersion:
        personalization = build_personalization(
            company=company,
            opportunity=opportunity,
            capability=capability,
            evidence=evidence,
            signals=signals,
            recipient=decision_maker,
            max_points=settings.outreach_max_personalization_points,
        )
        strategy = build_strategy(
            personalization=personalization,
            capability=capability,
            tone=outreach.tone,
            message_length=outreach.message_length,
            is_follow_up=is_follow_up,
            requested_objective=objective,
        )

        days_since = None
        if previous is not None and previous.sent_at:
            sent = previous.sent_at if previous.sent_at.tzinfo else previous.sent_at.replace(tzinfo=UTC)
            days_since = max(0, (datetime.now(UTC) - sent).days)

        context = WriterContext(
            # Trimmed of discovery artefacts; the user can still edit it.
            company_name=email_display_name(company),
            personalization=personalization,
            strategy=strategy,
            capability_name=capability.name,
            capability_description=capability.description,
            sender_name=sender.name,
            sender_company=sender.company,
            sender_signature=sender.signature,
            previous_subject=previous.subject if previous else None,
            previous_body=previous.body if previous else None,
            days_since_sent=days_since,
        )

        composed: ComposedEmail = (
            await self.writer.generate_follow_up(context)
            if is_follow_up
            else await self.writer.generate_outreach(context)
        )

        excerpts = {item.id: (item.excerpt or "") for item in evidence}
        result = validate_outreach(
            email=composed,
            claims=composed.claims,
            personalization=personalization,
            evidence_excerpts=excerpts,
            recipient_email=outreach.to_email,
            capability_exists=True,
            # A missing address blocks the Gmail draft, not the draft itself.
            allow_missing_recipient=True,
        )

        outreach.objective = strategy.objective
        outreach.subject = composed.subject
        outreach.body = composed.body
        outreach.ai_generated_subject = composed.subject
        outreach.ai_generated_body = composed.body
        outreach.user_edited = False
        outreach.strategy = strategy.dict()
        outreach.personalization = personalization.dict()
        outreach.validation = result.dict()
        outreach.generated_by = str(method)
        if outreach.status == OutreachStatus.DRAFT:
            outreach.status = OutreachStatus.REVIEW

        version = await self._store_version(
            outreach,
            composed=composed,
            strategy=strategy.dict(),
            personalization=personalization.dict(),
            validation=result.dict(),
            method=method,
        )

        await audit.record(
            self.session,
            action=AuditAction.EMAIL_GENERATED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={
                "version": version.version_number,
                "method": str(method),
                "valid": result.valid,
                "evidence_ids": personalization.evidence_ids,
            },
        )
        return version

    async def _store_version(
        self,
        outreach: Outreach,
        *,
        composed: ComposedEmail,
        strategy: dict,
        personalization: dict,
        validation: dict,
        method: str,
    ) -> OutreachVersion:
        await self.versions.deactivate_all(outreach.id)
        number = await self.versions.next_number(outreach.id)

        version = OutreachVersion(
            outreach_id=outreach.id,
            version_number=number,
            subject=composed.subject,
            body=composed.body,
            generation_method=str(method),
            strategy=strategy,
            personalization=personalization,
            validation=validation,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.session.add(version)
        await self.session.flush()

        # Claims are rows with real foreign keys, so a sentence can never
        # drift away from the evidence that justified it.
        for claim in composed.claims:
            row = OutreachClaim(
                outreach_version_id=version.id,
                text=claim.text,
                kind=str(claim.kind),
                requires_evidence=claim.requires_evidence,
            )
            self.session.add(row)
            await self.session.flush()
            for evidence_id in claim.evidence_ids:
                self.session.add(
                    OutreachClaimEvidence(claim_id=row.id, evidence_id=evidence_id)
                )

        outreach.active_version_id = version.id
        await self.session.flush()
        return version

    # ------------------------------------------------------------------ #
    # editing, versions, approval
    # ------------------------------------------------------------------ #

    async def apply_edit(
        self,
        outreach_id: int,
        *,
        subject: str | None = None,
        body: str | None = None,
        to_email: str | None = None,
        to_name: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        actor: str | None = None,
    ) -> Outreach:
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")
        if outreach.status in (OutreachStatus.SENT, OutreachStatus.COMPLETED):
            raise ConflictError("An outreach that has been sent can no longer be edited.")

        content_changed = False
        if subject is not None and subject != outreach.subject:
            outreach.subject = subject
            content_changed = True
        if body is not None and body != outreach.body:
            outreach.body = body
            content_changed = True

        if to_email is not None:
            outreach.to_email = to_email.strip() or None
        if to_name is not None:
            outreach.to_name = to_name.strip() or None
        if cc is not None:
            outreach.cc = cc.strip() or None
        if bcc is not None:
            outreach.bcc = bcc.strip() or None

        if content_changed:
            outreach.user_edited = True
            # An edited message has not been reviewed in its current form.
            if outreach.status in (OutreachStatus.APPROVED, OutreachStatus.GMAIL_DRAFT_CREATED):
                outreach.status = OutreachStatus.REVIEW
                outreach.approved_at = None
            await self._store_user_version(outreach)

        await self._revalidate(outreach)
        await audit.record(
            self.session,
            action=AuditAction.EMAIL_EDITED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={"content_changed": content_changed},
        )
        await self.session.commit()
        return outreach

    async def _store_user_version(self, outreach: Outreach) -> OutreachVersion:
        """Snapshot the user's text. Claims are not copied: the user wrote
        this, so the system does not assert evidence backing for it."""
        await self.versions.deactivate_all(outreach.id)
        number = await self.versions.next_number(outreach.id)
        version = OutreachVersion(
            outreach_id=outreach.id,
            version_number=number,
            subject=outreach.subject,
            body=outreach.body,
            generation_method=GenerationMethod.USER_EDIT,
            strategy=outreach.strategy,
            personalization=outreach.personalization,
            validation={},
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.session.add(version)
        await self.session.flush()
        outreach.active_version_id = version.id
        return version

    async def _revalidate(self, outreach: Outreach) -> ValidationResult:
        """Re-run checks against the current text.

        User-written text has no claim rows, so evidence binding cannot be
        verified for it — the language and structure checks still apply, and
        the result says which applied.
        """
        version = (
            await self.versions.get(outreach.active_version_id)
            if outreach.active_version_id
            else None
        )
        claims = (
            [
                ComposedClaim(
                    text=claim.text,
                    kind=claim.kind,
                    evidence_ids=[link.evidence_id for link in claim.evidence_links],
                )
                for claim in version.claims
            ]
            if version
            else []
        )

        personalization_dict = outreach.personalization or {}
        personalization = PersonalizationData(
            recipient=personalization_dict.get("recipient", {}),
            company_reference=personalization_dict.get("company_reference"),
            business_signal=personalization_dict.get("business_signal"),
            relevant_ubm_capability=personalization_dict.get("relevant_ubm_capability", {}),
            conversation_angle=personalization_dict.get("conversation_angle", ""),
            points=[
                PersonalizationPoint(**point) for point in personalization_dict.get("points", [])
            ],
            uncertainties=personalization_dict.get("uncertainties", []),
        )

        evidence_ids = personalization.evidence_ids
        excerpts: dict[int, str] = {}
        if evidence_ids:
            rows = await self.session.scalars(
                select(Evidence).where(Evidence.id.in_(evidence_ids))
            )
            excerpts = {row.id: (row.excerpt or "") for row in rows}

        composed = ComposedEmail(
            subject=outreach.subject or "",
            greeting="",
            body_paragraphs=[outreach.body or ""],
            call_to_action=(outreach.body or "").strip().splitlines()[-1] if outreach.body else "",
            signature="",
            claims=claims,
        )
        capability_exists = True
        if outreach.opportunity_id:
            opportunity = await self.session.get(Opportunity, outreach.opportunity_id)
            capability_exists = bool(
                opportunity and await self.capabilities.get(opportunity.capability_id)
            )

        result = validate_outreach(
            email=composed,
            claims=claims,
            personalization=personalization,
            evidence_excerpts=excerpts,
            recipient_email=outreach.to_email,
            capability_exists=capability_exists,
            allow_missing_recipient=True,
        )
        if outreach.user_edited:
            result.warnings.append(
                ValidationIssue(
                    "user_edited",
                    "This message was edited by hand, so evidence binding could not be "
                    "verified for the edited text.",
                )
            )
        outreach.validation = result.dict()
        return result

    async def activate_version(
        self, outreach_id: int, version_id: int, *, actor: str | None = None
    ) -> Outreach:
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")
        version = await self.versions.get(version_id)
        if version is None or version.outreach_id != outreach_id:
            raise NotFoundError(f"Version {version_id} does not belong to this outreach")

        await self.versions.deactivate_all(outreach_id)
        version.is_active = True
        outreach.active_version_id = version.id
        outreach.subject = version.subject
        outreach.body = version.body
        outreach.user_edited = version.generation_method == GenerationMethod.USER_EDIT
        outreach.strategy = version.strategy or outreach.strategy
        outreach.personalization = version.personalization or outreach.personalization
        if outreach.status in (OutreachStatus.APPROVED, OutreachStatus.GMAIL_DRAFT_CREATED):
            outreach.status = OutreachStatus.REVIEW
            outreach.approved_at = None

        await self._revalidate(outreach)
        await audit.record(
            self.session,
            action=AuditAction.VERSION_ACTIVATED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={"version": version.version_number},
        )
        await self.session.commit()
        return outreach

    async def approve(self, outreach_id: int, *, actor: str | None = None) -> Outreach:
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")

        outreach_state.ensure_transition(outreach.status, OutreachStatus.APPROVED)
        result = await self._revalidate(outreach)
        if not result.valid:
            raise ValidationError(
                "This outreach cannot be approved while it has validation errors.",
                details={"errors": [issue.dict() for issue in result.errors]},
            )

        outreach.status = OutreachStatus.APPROVED
        outreach.approved_at = datetime.now(UTC)
        await audit.record(
            self.session,
            action=AuditAction.EMAIL_APPROVED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
        )
        await self.session.commit()
        return outreach

    async def reject(
        self, outreach_id: int, *, reason: str | None = None, actor: str | None = None
    ) -> Outreach:
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")
        outreach_state.ensure_transition(outreach.status, OutreachStatus.REJECTED)
        outreach.status = OutreachStatus.REJECTED
        await audit.record(
            self.session,
            action=AuditAction.EMAIL_REJECTED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={"reason": reason} if reason else {},
        )
        await self.session.commit()
        return outreach

    async def cancel(self, outreach_id: int, *, actor: str | None = None) -> Outreach:
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")
        outreach_state.ensure_transition(outreach.status, OutreachStatus.CANCELLED)
        outreach.status = OutreachStatus.CANCELLED
        outreach.cancelled_at = datetime.now(UTC)
        await audit.record(
            self.session,
            action=AuditAction.OUTREACH_CANCELLED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
        )
        await self.session.commit()
        return outreach

    # ------------------------------------------------------------------ #
    # Gmail draft
    # ------------------------------------------------------------------ #

    async def create_gmail_draft(
        self, outreach_id: int, *, force_new: bool = False, actor: str | None = None
    ) -> Outreach:
        """Create a draft in the connected mailbox. Never sends.

        Clicking twice reuses the existing draft unless a new one is
        explicitly requested.
        """
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")

        outreach_state.ensure_can_create_gmail_draft(outreach.status)

        if outreach.gmail_draft_id and not force_new:
            provider = await self.delivery()
            existing = await provider.get_draft(outreach.gmail_draft_id)
            if existing is not None:
                return outreach
            # The draft was deleted in Gmail; fall through and make a new one.

        result = await self._revalidate(outreach)
        # An address is mandatory here, unlike at generation time.
        if not outreach.to_email:
            raise ValidationError(
                "This outreach has no recipient email address. Add one before creating "
                "a Gmail draft — an address is never derived from a person's name.",
                details={"field": "to_email"},
            )
        if not result.valid:
            raise ValidationError(
                "This outreach has validation errors and cannot be sent to Gmail.",
                details={"errors": [issue.dict() for issue in result.errors]},
            )

        sender = (
            await self.senders.get(outreach.sender_profile_id)
            if outreach.sender_profile_id
            else None
        )
        provider = await self.delivery()
        draft = await provider.create_draft(
            DraftMessage(
                to=outreach.to_email,
                subject=outreach.subject or "",
                body=outreach.body or "",
                cc=outreach.cc,
                bcc=outreach.bcc,
                from_name=sender.name if sender else None,
                thread_id=outreach.gmail_thread_id,
            )
        )

        outreach.gmail_draft_id = draft.draft_id
        outreach.gmail_draft_url = draft.url
        outreach.gmail_thread_id = draft.thread_id
        outreach.gmail_draft_created_at = datetime.now(UTC)
        # Explicitly *not* "sent": a draft exists, nothing has gone out.
        outreach.status = OutreachStatus.GMAIL_DRAFT_CREATED

        await audit.record(
            self.session,
            action=AuditAction.GMAIL_DRAFT_CREATED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={"gmail_draft_id": draft.draft_id},
        )
        await self.session.commit()
        return outreach

    async def mark_sent(
        self, outreach_id: int, *, sent_at: datetime | None = None, actor: str | None = None
    ) -> Outreach:
        """Record that a human sent the message from their mail client.

        The system does not observe the send; it records what the user says
        happened, which is why the status is only reachable by this action.
        """
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")

        outreach_state.ensure_can_mark_sent(outreach.status)

        outreach.sent_at = sent_at or datetime.now(UTC)
        outreach.status = OutreachStatus.SENT
        outreach.next_follow_up_at = await self._next_follow_up_at(outreach)

        await audit.record(
            self.session,
            action=AuditAction.MARKED_SENT,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={"sent_at": outreach.sent_at.isoformat()},
        )
        await self.session.commit()
        return outreach

    async def _next_follow_up_at(
        self, outreach: Outreach, *, index: int | None = None
    ) -> datetime | None:
        """When the next follow-up falls due.

        ``index`` is how many follow-ups already exist for this thread, which
        is counted from the child rows rather than stored on the parent —
        ``follow_up_number`` means "this message *is* follow-up N".
        """
        intervals = (
            outreach.campaign.follow_up_intervals
            if outreach.campaign and outreach.campaign.follow_up_intervals
            else settings.follow_up_interval_days
        )
        if index is None:
            index = len(await self.outreach.follow_ups_of(outreach.id))
        if index >= len(intervals):
            return None
        base = outreach.sent_at or datetime.now(UTC)
        if base.tzinfo is None:
            base = base.replace(tzinfo=UTC)
        return base + timedelta(days=int(intervals[index]))

    # ------------------------------------------------------------------ #
    # follow-ups
    # ------------------------------------------------------------------ #

    async def create_follow_up(
        self, outreach_id: int, *, actor: str | None = None
    ) -> Outreach:
        """Prepare a follow-up as its own outreach, linked to the original."""
        parent = await self.outreach.get(outreach_id)
        if parent is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")
        if parent.status not in (OutreachStatus.SENT, OutreachStatus.FOLLOW_UP_DUE):
            raise ConflictError(
                "A follow-up can only be prepared once the original has been marked as sent."
            )

        siblings = await self.outreach.follow_ups_of(parent.id)
        next_number = len(siblings) + 1

        opportunity = await self.session.get(Opportunity, parent.opportunity_id)
        if opportunity is None:
            raise NotFoundError("The opportunity behind this outreach no longer exists")
        await self.session.refresh(opportunity, ["evidence_links", "signal_links"])

        decision_maker = (
            await self.session.get(DecisionMaker, parent.decision_maker_id)
            if parent.decision_maker_id
            else None
        )
        if decision_maker:
            await self.session.refresh(decision_maker, ["source"])

        sender = (
            await self.senders.get(parent.sender_profile_id)
            if parent.sender_profile_id
            else None
        ) or await self.ensure_sender_profile()
        company, capability, evidence, signals = await self._load_context(
            opportunity, decision_maker
        )

        follow_up = await self.outreach.create(
            company_id=parent.company_id,
            opportunity_id=parent.opportunity_id,
            decision_maker_id=parent.decision_maker_id,
            campaign_id=parent.campaign_id,
            sender_profile_id=parent.sender_profile_id,
            parent_outreach_id=parent.id,
            follow_up_number=next_number,
            status=OutreachStatus.DRAFT,
            tone=parent.tone,
            message_length=MessageLength.SHORT,  # follow-ups are shorter
            to_email=parent.to_email,
            to_name=parent.to_name,
            cc=parent.cc,
            owner=parent.owner,
            gmail_thread_id=parent.gmail_thread_id,
        )
        await self.session.flush()

        await self._generate(
            follow_up,
            opportunity=opportunity,
            company=company,
            capability=capability,
            evidence=evidence,
            signals=signals,
            decision_maker=decision_maker,
            sender=sender,
            method=GenerationMethod.DETERMINISTIC
            if self.writer.name == "deterministic"
            else GenerationMethod.AI,
            objective=None,
            actor=actor,
            is_follow_up=True,
            previous=parent,
        )

        # The parent's next follow-up date moves on. Its own
        # follow_up_number stays 0: it is the original message, not a follow-up.
        parent.next_follow_up_at = await self._next_follow_up_at(parent, index=next_number)
        parent.status = (
            OutreachStatus.FOLLOW_UP_DUE if parent.next_follow_up_at else OutreachStatus.SENT
        )

        await audit.record(
            self.session,
            action=AuditAction.FOLLOW_UP_CREATED,
            object_type="outreach",
            object_id=follow_up.id,
            actor=actor,
            detail={"parent_outreach_id": parent.id, "follow_up_number": next_number},
        )
        await self.session.commit()
        return follow_up

    # ------------------------------------------------------------------ #
    # outcomes
    # ------------------------------------------------------------------ #

    async def record_outcome(
        self,
        outreach_id: int,
        *,
        status: str,
        reason: str | None = None,
        notes: str | None = None,
        actor: str | None = None,
    ) -> Outreach:
        outreach = await self.outreach.get(outreach_id)
        if outreach is None:
            raise NotFoundError(f"Outreach {outreach_id} not found")

        outreach.outcome_status = str(status)
        outreach.outcome_reason = str(reason) if reason else None
        outreach.outcome_notes = notes
        outreach.outcome_updated_at = datetime.now(UTC)

        self.session.add(
            OutreachOutcome(
                outreach_id=outreach.id,
                status=str(status),
                reason=str(reason) if reason else None,
                notes=notes,
                recorded_by=actor,
                created_at=datetime.now(UTC),
            )
        )

        # A terminal outcome closes the outreach and stops follow-up chasing.
        if status in (
            OutcomeStatus.NOT_INTERESTED,
            OutcomeStatus.OPPORTUNITY_WON,
            OutcomeStatus.OPPORTUNITY_LOST,
            OutcomeStatus.DO_NOT_CONTACT,
            OutcomeStatus.MEETING_SCHEDULED,
        ):
            if outreach.status in (OutreachStatus.SENT, OutreachStatus.FOLLOW_UP_DUE):
                outreach.status = OutreachStatus.COMPLETED
            outreach.next_follow_up_at = None

        await audit.record(
            self.session,
            action=AuditAction.OUTCOME_UPDATED,
            object_type="outreach",
            object_id=outreach.id,
            actor=actor,
            detail={"status": str(status), "reason": str(reason) if reason else None},
        )
        await self.session.commit()
        return outreach
