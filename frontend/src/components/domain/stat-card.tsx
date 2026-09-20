import type * as React from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/states";
import { formatNumber } from "@/lib/format";

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  loading,
}: {
  label: string;
  value: number | null;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  loading?: boolean;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-subtle">{label}</p>
        {Icon ? <Icon className="size-4 text-subtle" /> : null}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-16" />
      ) : (
        <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-foreground">
          {formatNumber(value)}
        </p>
      )}
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}
