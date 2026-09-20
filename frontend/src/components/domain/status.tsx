import { Badge } from "@/components/ui/badge";
import { humanize } from "@/lib/format";
import type { CompanyStatus, RunStatus } from "@/lib/types";

const RUN_TONES: Record<RunStatus, "neutral" | "accent" | "success" | "danger"> = {
  queued: "neutral",
  running: "accent",
  completed: "success",
  failed: "danger",
};

const COMPANY_TONES: Record<CompanyStatus, "neutral" | "accent" | "success" | "danger"> = {
  discovered: "neutral",
  researching: "accent",
  researched: "success",
  research_failed: "danger",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <Badge tone={RUN_TONES[status] ?? "neutral"}>
      {status === "running" || status === "queued" ? (
        <span className="size-1.5 animate-pulse rounded-full bg-current" aria-hidden />
      ) : null}
      {humanize(status)}
    </Badge>
  );
}

export function CompanyStatusBadge({ status }: { status: CompanyStatus }) {
  return <Badge tone={COMPANY_TONES[status] ?? "neutral"}>{humanize(status)}</Badge>;
}

export function PageTypeBadge({ type }: { type: string }) {
  return <Badge tone={type === "home" ? "accent" : "neutral"}>{humanize(type)}</Badge>;
}
