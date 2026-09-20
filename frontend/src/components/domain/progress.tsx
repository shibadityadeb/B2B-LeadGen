import { cn } from "@/lib/utils";

const STAGE_LABELS: Record<string, string> = {
  pending: "Queued",
  generating_queries: "Generating search queries…",
  searching: "Searching the web…",
  normalizing: "Normalizing companies…",
  saving: "Saving results…",
  done: "Completed",
};

export function stageLabel(stage: string, status: string): string {
  if (status === "failed") return "Failed";
  if (status === "queued") return "Waiting to start…";
  return STAGE_LABELS[stage] ?? "Working…";
}

export function ProgressBar({
  value,
  tone = "accent",
  className,
}: {
  value: number;
  tone?: "accent" | "success" | "danger";
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const background =
    tone === "success" ? "bg-success" : tone === "danger" ? "bg-danger" : "bg-accent";

  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-muted", className)}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-500", background)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
