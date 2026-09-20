"use client";

import { AlertTriangle, CircleHelp, Clock, Info } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import { ESTIMATED_DATE_HELP, plain } from "@/lib/plain";
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
  // An undated page tells us when we fetched it, not when it happened.
  const estimated = basis && basis !== "published_at";
  const word = plain.recency(level);
  const title = estimated
    ? ESTIMATED_DATE_HELP
    : ageDays !== null && ageDays !== undefined
      ? `${ageDays} day(s) ago`
      : word.help;

  return (
    <Badge tone={estimated ? "neutral" : FRESHNESS_TONE[level]} title={title}>
      <Clock className="size-3" />
      {estimated ? "Date not shown" : word.label}
    </Badge>
  );
}

/** Plain names for the confidence components. */
const COMPONENT_LABELS: Record<string, string> = {
  source_quality: "Source quality",
  source_count: "How many sources",
  recency: "How recent",
  directness: "Stated outright",
  agreement: "Sources agree",
};

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
        <Badge tone={CONFIDENCE_TONE[level]} title={plain.strength(level).help}>
          {plain.strength(level).label}
          {hasBreakdown ? <Info className="size-3 opacity-70" /> : null}
        </Badge>
      </button>

      {open && hasBreakdown ? (
        <div className="absolute right-0 top-full z-20 mt-1.5 w-72 rounded-lg border border-border bg-surface p-3 text-left shadow-lg">
          <p className="mb-2 text-xs font-medium text-foreground">
            Why we rated it this way
          </p>
          <p className="mb-2 text-xs text-muted">
            This scores how good the supporting information is — not whether the
            conclusion is true.
          </p>
          <dl className="space-y-1.5">
            {Object.entries(components).map(([key, value]) => (
              <div key={key} className="flex items-center gap-2">
                <dt className="w-28 shrink-0 text-xs text-muted">{COMPONENT_LABELS[key] ?? humanize(key)}</dt>
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

export function EpistemicBadge({ status }: { status: EpistemicStatus }) {
  const word = plain.certainty(status);
  return (
    <Badge tone={EPISTEMIC_TONE[status]} title={word.help}>
      {word.label}
    </Badge>
  );
}

const OPPORTUNITY_TONE: Record<OpportunityStatus, "success" | "accent" | "warning" | "neutral"> = {
  supported: "success",
  candidate: "accent",
  uncertain: "warning",
  dismissed: "neutral",
};

export function OpportunityStatusBadge({ status }: { status: OpportunityStatus }) {
  const word = plain.opportunityStanding(status);
  return (
    <Badge tone={OPPORTUNITY_TONE[status]} title={word.help}>
      {word.label}
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
  const word = plain.visibility(state);
  if (state === "not_found") {
    return (
      <Badge tone="warning" title={word.help}>
        <AlertTriangle className="size-3" />
        {word.label}
      </Badge>
    );
  }
  if (state === "new" || state === "updated") {
    return (
      <Badge tone="accent" title={word.help}>
        {word.label}
      </Badge>
    );
  }
  return (
    <Badge tone="neutral" title={word.help}>
      {word.label}
    </Badge>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  const word = plain.personTrust(status);
  if (status === "role_only") {
    return (
      <Badge tone="warning" title={word.help}>
        <CircleHelp className="size-3" />
        {word.label}
      </Badge>
    );
  }
  return (
    <Badge tone={status === "public_company_source" ? "success" : "neutral"} title={word.help}>
      {word.label}
    </Badge>
  );
}
