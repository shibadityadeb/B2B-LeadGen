"use client";

import { ChevronRight } from "lucide-react";
import type * as React from "react";

import { ConfidenceBadge, FreshnessBadge, ObservationBadge } from "@/components/domain/research-badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { formatDate } from "@/lib/format";
import { plain } from "@/lib/plain";
import type { Signal } from "@/lib/types";

export function SignalList({
  signals,
  onViewEvidence,
  emptyAction,
  hasBeenResearched = false,
}: {
  signals: Signal[];
  onViewEvidence: (signal: Signal) => void;
  emptyAction?: React.ReactNode;
  hasBeenResearched?: boolean;
}) {
  if (signals.length === 0) {
    return (
      <Card>
        <EmptyState
          title={hasBeenResearched ? "Nothing much happening" : "Not looked yet"}
          description={
            hasBeenResearched
              ? "We could not see any recent activity worth flagging. Some companies simply publish very little."
              : "Anything this company appears to be doing will show up here once we have looked."
          }
          action={emptyAction}
        />
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {signals.map((signal) => (
        <Card key={signal.id} className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-foreground">
                {plain.activity(signal.signal_type)}
              </h3>
              <p className="mt-1 text-sm text-muted">{signal.description}</p>
            </div>
            <ObservationBadge state={signal.observation_state} />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <FreshnessBadge freshness={signal.freshness} />
            <ConfidenceBadge
              level={signal.confidence_level}
              breakdown={signal.confidence_components}
            />
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-subtle">
              Based on {signal.evidence_count}{" "}
              {signal.evidence_count === 1 ? "thing we found" : "things we found"} across{" "}
              {signal.confidence_components?.distinct_sources ?? 1}{" "}
              {(signal.confidence_components?.distinct_sources ?? 1) === 1 ? "source" : "sources"}
              {signal.latest_evidence_at
                ? ` · most recent ${formatDate(signal.latest_evidence_at)}`
                : ""}
            </p>
            <Button variant="secondary" size="sm" onClick={() => onViewEvidence(signal)}>
              Show me <ChevronRight />
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
