"use client";

import { ChevronRight, Layers, Mail } from "lucide-react";
import * as React from "react";

import {
  ConfidenceBadge,
  FreshnessBadge,
  OpportunityStatusBadge,
} from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Opportunity } from "@/lib/types";

/**
 * An opportunity is presented as a hypothesis: what was observed, which UBM
 * capability it may touch, and how to check it. Deliberately not a score or
 * a "hot lead" banner — the reasoning is the product.
 */
export function OpportunityCard({
  opportunity,
  onViewEvidence,
  onDismiss,
  onRestore,
  onCreateOutreach,
  busy,
  outreachBusy,
  existingOutreachId,
}: {
  opportunity: Opportunity;
  onViewEvidence: (opportunity: Opportunity) => void;
  onDismiss?: (opportunity: Opportunity) => void;
  onRestore?: (opportunity: Opportunity) => void;
  onCreateOutreach?: (opportunity: Opportunity) => void;
  busy?: boolean;
  outreachBusy?: boolean;
  existingOutreachId?: number;
}) {
  const dismissed = opportunity.status === "dismissed";

  return (
    <Card className={dismissed ? "opacity-60" : undefined}>
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-wide text-subtle">
              Potential opportunity
            </p>
            <h3 className="mt-0.5 text-base font-semibold text-foreground">
              {opportunity.title}
            </h3>
          </div>
          <OpportunityStatusBadge status={opportunity.status} />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge tone="accent">
            <Layers className="size-3" />
            {opportunity.capability_name}
          </Badge>
          {opportunity.capability_category ? (
            <Badge tone="neutral">{opportunity.capability_category}</Badge>
          ) : null}
        </div>

        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-subtle">
            Why this may be relevant
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted">{opportunity.why_relevant}</p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <Badge tone="neutral">
            {opportunity.evidence_count}{" "}
            {opportunity.evidence_count === 1 ? "evidence item" : "evidence items"}
          </Badge>
          <FreshnessBadge freshness={opportunity.freshness} />
          <ConfidenceBadge
            level={opportunity.confidence_level}
            breakdown={opportunity.confidence_components}
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onViewEvidence(opportunity)}
            disabled={opportunity.evidence_count === 0}
          >
            View evidence <ChevronRight />
          </Button>
          {onCreateOutreach && !dismissed ? (
            <Button
              size="sm"
              onClick={() => onCreateOutreach(opportunity)}
              loading={outreachBusy}
              title={
                existingOutreachId
                  ? "Open the outreach already prepared for this opportunity"
                  : "Prepare a message for review. Nothing is sent."
              }
            >
              <Mail /> {existingOutreachId ? "Open outreach" : "Create outreach"}
            </Button>
          ) : null}
          {dismissed
            ? onRestore && (
                <Button variant="ghost" size="sm" onClick={() => onRestore(opportunity)} loading={busy}>
                  Restore
                </Button>
              )
            : onDismiss && (
                <Button variant="ghost" size="sm" onClick={() => onDismiss(opportunity)} loading={busy}>
                  Dismiss
                </Button>
              )}
        </div>
      </div>
    </Card>
  );
}
