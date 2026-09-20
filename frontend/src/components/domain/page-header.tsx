import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import type * as React from "react";

export function PageHeader({
  title,
  description,
  actions,
  backHref,
  backLabel,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <header className="mb-6">
      {backHref ? (
        <Link
          href={backHref}
          className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-3.5" />
          {backLabel ?? "Back"}
        </Link>
      ) : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {description ? (
            <div className="mt-1.5 text-sm text-muted">{description}</div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
