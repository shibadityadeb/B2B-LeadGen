"use client";

import { ChevronRight } from "lucide-react";

import { ConfidenceBadge, FreshnessBadge, ObservationBadge } from "@/components/domain/research-badges";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { formatDate } from "@/lib/format";
import type { Signal } from "@/lib/types";

export function SignalList({
  signals,
  onViewEvidence,
}: {
  signals: Signal[];
  onViewEvidence: (signal: Signal) => void;
}) {
  if (signals.length === 0) {
    return (
      <Card>
        <EmptyState
          title="No business signals yet"
          description="Signals are grouped from evidence. Run research to collect evidence first."
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
              <h3 className="text-sm font-semibold text-foreground">{signal.title}</h3>
              <p className="mt-1 text-sm text-muted">{signal.description}</p>
            </div>
            <ObservationBadge state={signal.observation_state} />
          </div>

          <div className="mt-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-subtle">Strength</span>
              <span className="h-1.5 w-32 overflow-hidden rounded-full bg-surface-muted">
                <span
                  className="block h-full rounded-full bg-accent"
                  style={{ width: `${Math.round(signal.strength * 100)}%` }}
                />
              </span>
              <span className="text-xs tabular-nums text-muted">
                {signal.strength.toFixed(2)}
              </span>
            </div>
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
              {signal.evidence_count} evidence item(s) ·{" "}
              {signal.confidence_components?.distinct_sources ?? 1} source(s)
              {signal.latest_evidence_at
                ? ` · latest ${formatDate(signal.latest_evidence_at)}`
                : ""}
            </p>
            <Button variant="ghost" size="sm" onClick={() => onViewEvidence(signal)}>
              View evidence <ChevronRight />
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
