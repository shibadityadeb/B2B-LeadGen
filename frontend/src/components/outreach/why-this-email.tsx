"use client";

import { AlertTriangle, ArrowRight, ExternalLink, Layers, Quote, User } from "lucide-react";

import { FreshnessBadge } from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, humanize, truncate } from "@/lib/format";
import type { OutreachDetail, PersonalizationData, OutreachStrategy } from "@/lib/types";

/**
 * The panel that differentiates this from an email tool: it shows the chain
 * company signal → evidence → UBM capability → recipient → message, so the
 * reviewer can see why the email exists before reading a word of it.
 */
export function WhyThisEmail({ outreach }: { outreach: OutreachDetail }) {
  const personalization = outreach.personalization as PersonalizationData;
  const strategy = outreach.strategy as OutreachStrategy;
  const points = personalization?.points ?? [];
  const capability = personalization?.relevant_ubm_capability;
  const recipient = personalization?.recipient;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Why this outreach exists</CardTitle>
        <Badge tone="neutral">{humanize(strategy?.objective ?? outreach.objective)}</Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* --- the chain --- */}
        <ol className="space-y-4">
          <Step
            index={1}
            label="Company signal"
            icon={Quote}
            empty="No public observation was available for this company."
          >
            {points.length > 0 ? (
              <ul className="space-y-3">
                {points.map((point) => (
                  <li key={point.evidence_ids.join("-")}>
                    <p className="text-sm font-medium text-foreground">
                      {point.observation}
                    </p>
                    <blockquote className="mt-1.5 rounded-lg border-l-2 border-accent-border bg-surface-muted/60 px-3 py-2 text-sm italic text-muted">
                      “{point.excerpt}”
                    </blockquote>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <FreshnessBadge
                        freshness={point.freshness as never}
                        basis={point.freshness_basis}
                      />
                      <Badge tone="neutral">{humanize(point.epistemic_status)}</Badge>
                      {point.published_at ? (
                        <span className="text-xs text-subtle">
                          {formatDate(point.published_at)}
                        </span>
                      ) : null}
                    </div>
                    {point.source_url ? (
                      <a
                        href={point.source_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="mt-1 inline-flex max-w-full items-center gap-1.5 text-xs text-accent hover:underline"
                      >
                        <span className="truncate">{truncate(point.source_url, 70)}</span>
                        <ExternalLink className="size-3 shrink-0" />
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </Step>

          <Step
            index={2}
            label="Relevant UBM capability"
            icon={Layers}
            empty="No capability is linked."
          >
            {capability ? (
              <>
                <p className="text-sm font-medium text-foreground">{capability.name}</p>
                <p className="mt-0.5 text-sm text-muted">{capability.description}</p>
              </>
            ) : null}
          </Step>

          <Step index={3} label="Recipient" icon={User} empty="No recipient selected.">
            {recipient ? (
              <>
                <p className="text-sm font-medium text-foreground">
                  {recipient.name ?? (
                    <span className="italic text-muted">Name not published</span>
                  )}
                </p>
                <p className="mt-0.5 text-sm text-muted">{recipient.role ?? "Role unknown"}</p>
                <p className="mt-1 text-xs text-subtle">
                  {recipient.email ?? "No public email address found"}
                </p>
              </>
            ) : null}
          </Step>
        </ol>

        {/* --- angle --- */}
        {personalization?.conversation_angle ? (
          <div className="rounded-lg border border-border bg-surface-muted/50 p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-subtle">
              Conversation angle
            </p>
            <p className="mt-1 text-sm text-foreground">
              {personalization.conversation_angle}
            </p>
          </div>
        ) : null}

        {/* --- uncertainties --- */}
        {personalization?.uncertainties?.length ? (
          <div className="rounded-lg border border-warning/40 bg-warning-soft/50 p-3">
            <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-warning">
              <AlertTriangle className="size-3.5" />
              What is uncertain
            </p>
            <ul className="mt-1.5 space-y-1">
              {personalization.uncertainties.map((note) => (
                <li key={note} className="text-sm text-muted">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Step({
  index,
  label,
  icon: Icon,
  empty,
  children,
}: {
  index: number;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  empty: string;
  children: React.ReactNode;
}) {
  const hasContent = Boolean(children);
  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-border bg-surface text-xs font-semibold text-muted">
          {index}
        </span>
        {index < 3 ? (
          <span className="mt-1 flex-1">
            <ArrowRight className="size-3 rotate-90 text-subtle" />
          </span>
        ) : null}
      </div>
      <div className="min-w-0 flex-1 pb-1">
        <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-subtle">
          <Icon className="size-3.5" />
          {label}
        </p>
        <div className="mt-1.5">
          {hasContent ? children : <p className="text-sm italic text-muted">{empty}</p>}
        </div>
      </div>
    </li>
  );
}
