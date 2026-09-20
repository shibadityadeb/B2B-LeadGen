"use client";

import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

import { ProgressBar } from "@/components/domain/progress";
import { ResearchStatusBadge } from "@/components/domain/research-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDuration } from "@/lib/format";
import type { ResearchRun } from "@/lib/types";

/** Stage labels mirror ResearchStage on the backend — real state, not theatre. */
const STAGE_LABELS: Record<string, string> = {
  pending: "Queued",
  loading_company: "Loading company…",
  collecting_pages: "Collecting pages already crawled…",
  discovering_sources: "Searching for public sources…",
  crawling_sources: "Retrieving sources…",
  extracting_evidence: "Extracting evidence…",
  deriving_signals: "Deriving business signals…",
  finding_people: "Looking for publicly listed people…",
  matching_capabilities: "Matching UBM capabilities…",
  writing_brief: "Writing the research brief…",
  done: "Completed",
};

export function ResearchProgress({
  run,
  onRetry,
  retrying,
}: {
  run: ResearchRun;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const active =
    run.status === "queued" || run.status === "researching" || run.status === "analyzing";

  if (run.status === "failed") {
    return (
      <Card className="border-danger/30 bg-danger-soft">
        <CardContent>
          <p className="flex items-center gap-2 text-sm font-medium text-danger">
            <AlertTriangle className="size-4" /> Research failed
          </p>
          <p className="mt-1.5 text-sm text-danger/90">
            {run.error_message ?? "No further detail was recorded."}
          </p>
          {onRetry ? (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry} loading={retrying}>
              Retry research
            </Button>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  if (!active) {
    return (
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-sm text-success">
            <CheckCircle2 className="size-4" />
            Research completed in {formatDuration(run.started_at, run.completed_at)}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            <span>{run.sources_retrieved} sources</span>
            <span>{run.evidence_count} evidence</span>
            <span>{run.signals_count} signals</span>
            <span>{run.opportunities_count} opportunities</span>
            {run.llm_used ? <span>LLM-assisted</span> : <span>deterministic</span>}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-accent-border bg-accent-soft/40">
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Loader2 className="size-4 animate-spin text-accent" />
            {STAGE_LABELS[run.stage] ?? "Working…"}
          </p>
          <ResearchStatusBadge status={run.status} />
        </div>
        <ProgressBar value={run.progress} />
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          <span>
            {run.sources_retrieved}/{run.sources_discovered} sources retrieved
          </span>
          <span>{run.evidence_count} evidence</span>
          <span>{run.signals_count} signals</span>
          <span>{run.opportunities_count} opportunities</span>
        </div>
      </CardContent>
    </Card>
  );
}
