"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} />;
}

/** Placeholder for a table while its first page loads. */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="divide-y divide-border" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex items-center gap-4 px-5 py-4">
          {Array.from({ length: columns }).map((_, columnIndex) => (
            <Skeleton
              key={columnIndex}
              className={cn("h-4", columnIndex === 0 ? "w-1/3" : "w-1/6")}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true">
      {Array.from({ length: count }).map((_, index) => (
        <Skeleton key={index} className="h-28 rounded-card" />
      ))}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-6 py-14 text-center",
        className,
      )}
    >
      {Icon ? (
        <div className="mb-4 flex size-11 items-center justify-center rounded-full border border-border bg-surface-muted">
          <Icon className="size-5 text-subtle" />
        </div>
      ) : null}
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {description ? (
        <p className="mt-1.5 max-w-md text-sm text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center px-6 py-12 text-center",
        className,
      )}
    >
      <div className="mb-4 flex size-11 items-center justify-center rounded-full bg-danger-soft">
        <AlertTriangle className="size-5 text-danger" />
      </div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {message ? <p className="mt-1.5 max-w-md text-sm text-muted">{message}</p> : null}
      {onRetry ? (
        <Button variant="secondary" size="sm" className="mt-5" onClick={onRetry}>
          <RefreshCw /> Try again
        </Button>
      ) : null}
    </div>
  );
}

/** Inline banner for non-blocking failures (e.g. an action that failed). */
export function InlineError({ message, className }: { message: string; className?: string }) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
