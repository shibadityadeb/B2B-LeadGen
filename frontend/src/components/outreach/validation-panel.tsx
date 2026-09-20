"use client";

import { AlertTriangle, CheckCircle2, Info } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ValidationResult } from "@/lib/types";

/**
 * Validation results, shown in full. A failure names the exact sentence that
 * caused it — the system never quietly rewrites an unsupported claim.
 */
export function ValidationPanel({ validation }: { validation: ValidationResult | null }) {
  const errors = validation?.errors ?? [];
  const warnings = validation?.warnings ?? [];

  if (!validation) return null;

  if (errors.length === 0 && warnings.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 text-sm text-success">
          <CheckCircle2 className="size-4" />
          All automated checks passed.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={errors.length ? "border-danger/30" : undefined}>
      <CardHeader>
        <CardTitle>Automated checks</CardTitle>
        <span className="text-xs text-subtle">
          {errors.length
            ? "These must be resolved before approval"
            : "Worth reading before approving"}
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        {errors.map((issue, index) => (
          <Issue key={`e-${index}`} tone="error" issue={issue} />
        ))}
        {warnings.map((issue, index) => (
          <Issue key={`w-${index}`} tone="warning" issue={issue} />
        ))}
      </CardContent>
    </Card>
  );
}

function Issue({
  tone,
  issue,
}: {
  tone: "error" | "warning";
  issue: { code: string; message: string; context: string | null };
}) {
  const isError = tone === "error";
  return (
    <div
      className={
        isError
          ? "rounded-lg border border-danger/30 bg-danger-soft px-3 py-2"
          : "rounded-lg border border-border bg-surface-muted/50 px-3 py-2"
      }
    >
      <p
        className={
          isError
            ? "flex items-start gap-2 text-sm text-danger"
            : "flex items-start gap-2 text-sm text-muted"
        }
      >
        {isError ? (
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
        ) : (
          <Info className="mt-0.5 size-3.5 shrink-0" />
        )}
        <span>{issue.message}</span>
      </p>
      {issue.context ? (
        <p className="mt-1.5 pl-5 text-xs italic text-subtle">“{issue.context}”</p>
      ) : null}
    </div>
  );
}
