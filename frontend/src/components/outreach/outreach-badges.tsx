"use client";

import { AlertTriangle, CheckCircle2, Clock, Mail, PenLine, Send } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import type { OutcomeStatus, OutreachStatus } from "@/lib/types";

const STATUS_TONE: Record<OutreachStatus, "neutral" | "accent" | "success" | "warning" | "danger"> = {
  draft: "neutral",
  review: "warning",
  approved: "accent",
  gmail_draft_created: "accent",
  sent: "success",
  follow_up_due: "warning",
  completed: "success",
  cancelled: "neutral",
  rejected: "danger",
};

const STATUS_LABEL: Record<OutreachStatus, string> = {
  draft: "Draft",
  review: "Awaiting review",
  approved: "Approved",
  gmail_draft_created: "Gmail draft created",
  sent: "Marked sent",
  follow_up_due: "Follow-up due",
  completed: "Completed",
  cancelled: "Cancelled",
  rejected: "Rejected",
};

const STATUS_HELP: Record<OutreachStatus, string> = {
  draft: "Being prepared.",
  review: "Generated and waiting for a human to approve it.",
  approved: "A person approved this wording. It has not been sent.",
  gmail_draft_created:
    "A draft exists in the connected mailbox. Nothing has been sent — you send it yourself from Gmail.",
  sent: "A person recorded that they sent this. The system does not observe sending.",
  follow_up_due: "The follow-up interval has elapsed.",
  completed: "Closed out.",
  cancelled: "Cancelled before going out.",
  rejected: "A reviewer rejected this wording.",
};

export function OutreachStatusBadge({ status }: { status: OutreachStatus }) {
  const Icon =
    status === "sent" ? Send : status === "gmail_draft_created" ? Mail : undefined;
  return (
    <Badge tone={STATUS_TONE[status] ?? "neutral"} title={STATUS_HELP[status]}>
      {Icon ? <Icon className="size-3" /> : null}
      {STATUS_LABEL[status] ?? humanize(status)}
    </Badge>
  );
}

const OUTCOME_TONE: Record<OutcomeStatus, "neutral" | "accent" | "success" | "warning" | "danger"> = {
  no_response: "neutral",
  replied: "accent",
  interested: "success",
  not_interested: "warning",
  meeting_scheduled: "success",
  opportunity_won: "success",
  opportunity_lost: "danger",
  do_not_contact: "danger",
};

export function OutcomeBadge({ status }: { status: OutcomeStatus }) {
  return <Badge tone={OUTCOME_TONE[status] ?? "neutral"}>{humanize(status)}</Badge>;
}

export function ValidationBadge({
  valid,
  errors,
  warnings,
}: {
  valid: boolean;
  errors: number;
  warnings: number;
}) {
  if (!valid) {
    return (
      <Badge tone="danger" title="This message cannot be approved until these are resolved.">
        <AlertTriangle className="size-3" />
        {errors} {errors === 1 ? "issue" : "issues"}
      </Badge>
    );
  }
  if (warnings > 0) {
    return (
      <Badge tone="warning" title="Worth reading before approving, but not blocking.">
        {warnings} {warnings === 1 ? "note" : "notes"}
      </Badge>
    );
  }
  return (
    <Badge tone="success">
      <CheckCircle2 className="size-3" />
      Checks passed
    </Badge>
  );
}

export function EditedBadge() {
  return (
    <Badge tone="neutral" title="Edited by hand. Evidence binding was not verified for your text.">
      <PenLine className="size-3" />
      Edited
    </Badge>
  );
}

export function FollowUpBadge({ due, at }: { due: boolean; at: string | null }) {
  if (!at) return null;
  return (
    <Badge tone={due ? "warning" : "neutral"}>
      <Clock className="size-3" />
      {due ? "Follow-up due" : "Follow-up scheduled"}
    </Badge>
  );
}
