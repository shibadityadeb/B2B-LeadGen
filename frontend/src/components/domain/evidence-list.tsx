"use client";

import { ExternalLink, EyeOff, Quote } from "lucide-react";
import * as React from "react";

import {
  ConfidenceBadge,
  EpistemicBadge,
  FreshnessBadge,
} from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { formatDate, hostname } from "@/lib/format";
import { plain } from "@/lib/plain";
import type { Evidence } from "@/lib/types";

/**
 * One thing we found, written for someone who is not technical.
 *
 * The quoted text is copied word for word from the page, and the Source
 * button opens that page — so the reader can check any claim themselves
 * rather than taking it on trust.
 */
export function EvidenceItem({ evidence }: { evidence: Evidence }) {
  const stale = evidence.observation_state === "not_found";

  return (
    <article className={`border-b border-border py-4 last:border-b-0 ${stale ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm font-medium text-foreground">{evidence.claim}</p>
        <Badge tone="neutral">{plain.findingKind(evidence.evidence_type)}</Badge>
      </div>

      {evidence.excerpt ? (
        <blockquote className="mt-2.5 flex gap-2 rounded-lg border-l-2 border-accent-border bg-surface-muted/60 px-3 py-2">
          <Quote className="mt-0.5 size-3.5 shrink-0 text-subtle" />
          <p className="text-sm italic text-muted">{evidence.excerpt}</p>
        </blockquote>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <EpistemicBadge status={evidence.epistemic_status} />
        <FreshnessBadge
          freshness={evidence.freshness}
          ageDays={evidence.age_days}
          basis={evidence.freshness_basis}
        />
        <ConfidenceBadge
          level={evidence.confidence_level}
          breakdown={evidence.confidence_components}
        />
        {stale ? (
          <Badge tone="warning" title={plain.visibility("not_found").help}>
            <EyeOff className="size-3" />
            No longer visible
          </Badge>
        ) : null}
      </div>

      {/* The source is the whole point — make it a real button, not a footnote. */}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {evidence.source?.url ? (
          <a
            href={evidence.source.url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border-strong bg-surface px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-accent-border hover:text-accent"
            title={evidence.source.url}
          >
            <ExternalLink className="size-3.5" />
            Source: {hostname(evidence.source.url)}
          </a>
        ) : null}
        <span className="text-xs text-subtle">
          {evidence.published_at
            ? `Published ${formatDate(evidence.published_at)}`
            : `Found ${formatDate(evidence.observed_at)}`}
        </span>
        {evidence.source?.reliability ? (
          <span
            className="text-xs text-subtle"
            title={plain.sourceTrust(evidence.source.reliability).help}
          >
            {plain.sourceTrust(evidence.source.reliability).label}
          </span>
        ) : null}
      </div>
    </article>
  );
}

export function EvidenceList({
  items,
  emptyTitle = "Nothing found yet",
  emptyDescription,
}: {
  items: Evidence[];
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  // Things we can no longer see on the web are kept on record but hidden by
  // default: showing a dozen struck-through items would mislead a reader who
  // has no reason to know what "no longer observed" means.
  const current = items.filter((item) => item.observation_state !== "not_found");
  const stale = items.filter((item) => item.observation_state === "not_found");
  const [showStale, setShowStale] = React.useState(false);

  if (items.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div>
      {current.length > 0 ? (
        current.map((item) => <EvidenceItem key={item.id} evidence={item} />)
      ) : (
        <EmptyState
          title="Nothing is currently showing"
          description="Everything we found earlier has since disappeared from the web. It is kept below for reference."
        />
      )}

      {stale.length > 0 ? (
        <div className="mt-4 border-t border-border pt-4">
          <Button variant="ghost" size="sm" onClick={() => setShowStale((value) => !value)}>
            <EyeOff />
            {showStale ? "Hide" : "Show"} {stale.length} older{" "}
            {stale.length === 1 ? "item" : "items"} we can no longer find
          </Button>
          {showStale ? (
            <div className="mt-2">
              <p className="mb-3 rounded-lg bg-surface-muted/60 px-3 py-2 text-xs text-muted">
                These were found in an earlier check but are not on the pages any more.
                They are kept for reference — do not rely on them.
              </p>
              {stale.map((item) => (
                <EvidenceItem key={item.id} evidence={item} />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
