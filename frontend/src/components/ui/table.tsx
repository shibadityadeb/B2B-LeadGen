import * as React from "react";

import { cn } from "@/lib/utils";

/** Horizontally scrollable on narrow screens rather than squashed. */
export function TableWrap({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("w-full overflow-x-auto", className)} {...props} />;
}

export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full min-w-[42rem] text-sm", className)} {...props} />;
}

export function Th({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "whitespace-nowrap border-b border-border bg-surface-muted/60 px-5 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-subtle",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("border-b border-border px-5 py-3.5 align-middle", className)} {...props} />
  );
}

export function Tr({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors hover:bg-surface-muted/50", className)} {...props} />;
}
