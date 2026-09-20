import Link from "next/link";
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
  return (
    <tr
      // `relative` anchors the stretched RowLink below, so the whole row is
      // clickable rather than just the small id cell.
      className={cn("relative transition-colors hover:bg-surface-muted/50", className)}
      {...props}
    />
  );
}

/**
 * The row's primary link. Its ::after covers the entire row, so a click
 * anywhere opens the record — while remaining a real anchor, so it is
 * keyboard-focusable and shows the destination on hover.
 *
 * Other links in the same row must use {@link RowInnerLink} to sit above it.
 */
export function RowLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "after:absolute after:inset-0 after:content-['']",
        "font-medium text-foreground hover:text-accent",
        className,
      )}
    >
      {children}
    </Link>
  );
}

/** A secondary link inside a row, lifted above the stretched RowLink. */
export function RowInnerLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={cn("relative z-10 hover:text-accent", className)}>
      {children}
    </Link>
  );
}
