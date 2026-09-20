"use client";

import { AlertTriangle, CircleHelp, Clock, Info } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import type {
  ConfidenceBreakdown,
  ConfidenceLevel,
  EpistemicStatus,
  FreshnessLevel,
  ObservationState,
  OpportunityStatus,
  ResearchStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const FRESHNESS_TONE: Record<FreshnessLevel, "success" | "accent" | "neutral" | "warning"> = {
  recent: "success",
  active: "accent",
  older: "neutral",
  stale: "warning",
  unknown: "neutral",
};

export function FreshnessBadge({
  freshness,
  ageDays,
  basis,
}: {
  freshness: FreshnessLevel | null;
  ageDays?: number | null;
  basis?: string | null;
}) {
  const level = (freshness ?? "unknown") as FreshnessLevel;
  // An undated page tells us when we fetched it, not when it happened —
  // say so rather than implying the event is fresh.
  const estimated = basis && basis !== "published_at";
  const title = estimated
    ? "No publication date on the source; age is measured from when the page was retrieved."
    : ageDays !== null && ageDays !== undefined
      ? `${ageDays} day(s) since publication`
      : undefined;

  return (
    <Badge tone={FRESHNESS_TONE[level]} title={title}>
      <Clock className="size-3" />
      {humanize(level)}
      {estimated ? <span className="opacity-70">·&nbsp;est.</span> : null}
    </Badge>
  );
}

const CONFIDENCE_TONE: Record<ConfidenceLevel, "success" | "accent" | "neutral"> = {
  high: "success",
  medium: "accent",
  low: "neutral",
};

export function ConfidenceBadge({
  level,
  breakdown,
}: {
  level: ConfidenceLevel;
  breakdown?: ConfidenceBreakdown;
}) {
  const [open, setOpen] = React.useState(false);
  const components = breakdown?.components ?? {};
  const hasBreakdown = Object.keys(components).length > 0;

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={() => hasBreakdown && setOpen((value) => !value)}
        className={cn("inline-flex", hasBreakdown ? "cursor-pointer" : "cursor-default")}
        aria-expanded={hasBreakdown ? open : undefined}
        title={hasBreakdown ? "Show how this was calculated" : undefined}
      >
        <Badge tone={CONFIDENCE_TONE[level]}>
          {humanize(level)} confidence
          {hasBreakdown ? <Info className="size-3 opacity-70" /> : null}
        </Badge>
      </button>

      {open && hasBreakdown ? (
        <div className="absolute right-0 top-full z-20 mt-1.5 w-72 rounded-lg border border-border bg-surface p-3 text-left shadow-lg">
          <p className="mb-2 text-xs font-medium text-foreground">
            Evidence quality, not certainty
          </p>
          <dl className="space-y-1.5">
            {Object.entries(components).map(([key, value]) => (
              <div key={key} className="flex items-center gap-2">
                <dt className="w-28 shrink-0 text-xs text-muted">{humanize(key)}</dt>
                <dd className="flex flex-1 items-center gap-2">
                  <span className="h-1 flex-1 overflow-hidden rounded-full bg-surface-muted">
                    <span
                      className="block h-full rounded-full bg-accent"
                      style={{ width: `${Math.round((value as number) * 100)}%` }}
                    />
                  </span>
                  <span className="w-8 text-right text-xs tabular-nums text-subtle">
                    {(value as number).toFixed(2)}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
          {breakdown?.notes?.length ? (
            <ul className="mt-2.5 space-y-1 border-t border-border pt-2.5">
              {breakdown.notes.map((note) => (
                <li key={note} className="text-xs text-muted">
                  {note}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </span>
  );
}

const EPISTEMIC_TONE: Record<EpistemicStatus, "success" | "accent" | "warning" | "neutral"> = {
  known: "success",
  inferred: "accent",
  possible: "warning",
  unknown: "neutral",
};

const EPISTEMIC_HELP: Record<EpistemicStatus, string> = {
  known: "Stated directly in the source text.",
  inferred: "Derived from the source rather than stated.",
  possible: "The source hedges — a plan or intention, not a completed event.",
  unknown: "Not established by the sources retrieved.",
};

export function EpistemicBadge({ status }: { status: EpistemicStatus }) {
  return (
    <Badge tone={EPISTEMIC_TONE[status]} title={EPISTEMIC_HELP[status]}>
      {humanize(status)}
    </Badge>
  );
}

const OPPORTUNITY_TONE: Record<OpportunityStatus, "success" | "accent" | "warning" | "neutral"> = {
  supported: "success",
  candidate: "accent",
  uncertain: "warning",
  dismissed: "neutral",
};

const OPPORTUNITY_HELP: Record<OpportunityStatus, string> = {
  supported: "Several signals, corroborated by more than one source.",
  candidate: "Worth looking into; not yet corroborated across sources.",
  uncertain: "Weak or thin evidence.",
  dismissed: "Dismissed by a reviewer. Later research will not revive it.",
};

export function OpportunityStatusBadge({ status }: { status: OpportunityStatus }) {
  return (
    <Badge tone={OPPORTUNITY_TONE[status]} title={OPPORTUNITY_HELP[status]}>
      {humanize(status)}
    </Badge>
  );
}

const RESEARCH_TONE: Record<ResearchStatus, "neutral" | "accent" | "success" | "danger"> = {
  not_started: "neutral",
  queued: "neutral",
  researching: "accent",
  analyzing: "accent",
  completed: "success",
  failed: "danger",
};

export function ResearchStatusBadge({ status }: { status: ResearchStatus }) {
  const busy = status === "researching" || status === "analyzing" || status === "queued";
  return (
    <Badge tone={RESEARCH_TONE[status]}>
      {busy ? <span className="size-1.5 animate-pulse rounded-full bg-current" /> : null}
      {status === "not_started" ? "Not researched" : humanize(status)}
    </Badge>
  );
}

export function ObservationBadge({ state }: { state: ObservationState }) {
  if (state === "new") return <Badge tone="accent">New</Badge>;
  if (state === "updated") return <Badge tone="accent">Updated</Badge>;
  if (state === "not_found")
    return (
      <Badge tone="warning" title="Not observed in the most recent research run. Kept on record.">
        <AlertTriangle className="size-3" />
        No longer found
      </Badge>
    );
  return (
    <Badge tone="neutral" title="Seen again in the most recent run.">
      Still present
    </Badge>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  if (status === "role_only") {
    return (
      <Badge tone="warning" title="A role was published without a name. No name was invented.">
        <CircleHelp className="size-3" />
        Role only
      </Badge>
    );
  }
  if (status === "public_company_source") {
    return <Badge tone="success" title="Read from the company's own public page.">Company source</Badge>;
  }
  return <Badge tone="neutral">{humanize(status)}</Badge>;
}
