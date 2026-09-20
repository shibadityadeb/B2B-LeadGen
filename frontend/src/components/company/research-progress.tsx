"use client";

import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

import { ProgressBar } from "@/components/domain/progress";
import { ResearchStatusBadge } from "@/components/domain/research-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatDuration } from "@/lib/format";
import type { ResearchRun } from "@/lib/types";

/**
 * What the system is doing, in words the operator will understand. These
 * mirror the real backend stages — the wording is plain, the progress is not
 * decorative.
 */
const STAGE_LABELS: Record<string, string> = {
  pending: "Getting ready…",
  loading_company: "Getting ready…",
  collecting_pages: "Gathering pages we already had…",
  discovering_sources: "Searching the web for mentions…",
  crawling_sources: "Reading the pages we found…",
  extracting_evidence: "Picking out what matters…",
  deriving_signals: "Working out what they're up to…",
  finding_people: "Looking for named contacts…",
  matching_capabilities: "Checking where UBM could fit…",
  writing_brief: "Writing the summary…",
  done: "Finished",
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
            <AlertTriangle className="size-4" /> We could not finish this check
          </p>
          <p className="mt-1.5 text-sm text-danger/90">
            {run.error_message ?? "No further detail was recorded."}
          </p>
          {onRetry ? (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry} loading={retrying}>
              Try again
            </Button>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  if (!active) {
    // A sentence, not a row of counters: the operator wants to know what
    // came of it, not how the pipeline is instrumented.
    return (
      <Card>
        <CardContent>
          <p className="flex items-start gap-2 text-sm text-foreground">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
            <span>
              We read <strong>{run.sources_retrieved}</strong>{" "}
              {run.sources_retrieved === 1 ? "page" : "pages"} and found{" "}
              <strong>{run.evidence_count}</strong>{" "}
              {run.evidence_count === 1 ? "thing" : "things"} worth noting, pointing to{" "}
              <strong>{run.opportunities_count}</strong>{" "}
              {run.opportunities_count === 1 ? "possible opening" : "possible openings"}.
            </span>
          </p>
          <p className="mt-1 pl-6 text-xs text-subtle">
            Checked {formatDuration(run.started_at, run.completed_at)} ago in real time
            {run.llm_used ? " · AI helped read the pages" : ""}
          </p>
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
        <p className="text-xs text-muted">
          {run.sources_retrieved} of {run.sources_discovered} pages read so far ·{" "}
          {run.evidence_count} {run.evidence_count === 1 ? "thing" : "things"} found
        </p>
      </CardContent>
    </Card>
  );
}
