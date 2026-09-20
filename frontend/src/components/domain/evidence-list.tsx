"use client";

import { ExternalLink, Quote } from "lucide-react";
import * as React from "react";

import {
  ConfidenceBadge,
  EpistemicBadge,
  FreshnessBadge,
  ObservationBadge,
} from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/states";
import { formatDate, humanize, truncate } from "@/lib/format";
import type { Evidence } from "@/lib/types";

/**
 * One evidence item. The excerpt is verbatim from the source and the URL is
 * always shown, so a reader can check the claim rather than trust it.
 */
export function EvidenceItem({ evidence }: { evidence: Evidence }) {
  return (
    <article className="border-b border-border py-4 last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-sm font-medium text-foreground">{evidence.claim}</p>
        <Badge tone="neutral">{humanize(evidence.evidence_type)}</Badge>
      </div>

      {evidence.excerpt ? (
        <blockquote className="mt-2.5 flex gap-2 rounded-lg border-l-2 border-accent-border bg-surface-muted/60 px-3 py-2">
          <Quote className="mt-0.5 size-3.5 shrink-0 text-subtle" />
          <p className="text-sm italic text-muted">{evidence.excerpt}</p>
        </blockquote>
      ) : null}

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
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
        <ObservationBadge state={evidence.observation_state} />
        {evidence.extractor !== "rules" ? (
          <Badge tone="neutral" title="Extracted by the language model and verified against the source text.">
            {evidence.extractor}
          </Badge>
        ) : null}
      </div>

      <dl className="mt-2.5 grid gap-x-6 gap-y-1 text-xs text-subtle sm:grid-cols-2">
        <div className="flex gap-1.5">
          <dt>Published:</dt>
          <dd className="text-muted">
            {evidence.published_at ? formatDate(evidence.published_at) : "not stated on the page"}
          </dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Observed:</dt>
          <dd className="text-muted">{formatDate(evidence.observed_at)}</dd>
        </div>
        {evidence.times_observed > 1 ? (
          <div className="flex gap-1.5">
            <dt>Seen in:</dt>
            <dd className="text-muted">{evidence.times_observed} research runs</dd>
          </div>
        ) : null}
      </dl>

      {evidence.source ? (
        <a
          href={evidence.source.url}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-2 inline-flex max-w-full items-center gap-1.5 text-xs text-accent hover:underline"
        >
          <span className="truncate">{truncate(evidence.source.url, 78)}</span>
          <ExternalLink className="size-3 shrink-0" />
        </a>
      ) : null}
    </article>
  );
}

export function EvidenceList({
  items,
  emptyTitle = "No evidence",
  emptyDescription,
}: {
  items: Evidence[];
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  if (items.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }
  return (
    <div>
      {items.map((item) => (
        <EvidenceItem key={item.id} evidence={item} />
      ))}
    </div>
  );
}
