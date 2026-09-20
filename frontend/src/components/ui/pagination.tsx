"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/format";

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  label = "results",
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  label?: string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col gap-3 border-t border-border px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs text-muted">
        {total === 0
          ? `No ${label}`
          : `Showing ${formatNumber(first)}–${formatNumber(last)} of ${formatNumber(total)} ${label}`}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft /> Previous
        </Button>
        <span className="px-1 text-xs tabular-nums text-muted">
          {page} / {pages}
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pages}
          aria-label="Next page"
        >
          Next <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
