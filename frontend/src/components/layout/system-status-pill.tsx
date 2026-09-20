"use client";

import Link from "next/link";
import useSWR from "swr";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Live dependency health, refreshed in the background. */
export function SystemStatusPill() {
  const { data, error, isLoading } = useSWR("status", api.status, {
    refreshInterval: 60_000,
    revalidateOnFocus: false,
  });

  const healthy = data?.healthy === true;
  const broken = data?.components.filter((c) => !c.connected && !c.optional) ?? [];

  const label = isLoading
    ? "Checking services…"
    : error || !data
      ? "API unreachable"
      : healthy
        ? "All services connected"
        : `${broken.length} service${broken.length === 1 ? "" : "s"} unavailable`;

  const tone = isLoading
    ? "bg-subtle"
    : healthy && !error
      ? "bg-success"
      : "bg-danger";

  return (
    <Link
      href="/settings"
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
    >
      <span
        className={cn("size-2 shrink-0 rounded-full", tone, isLoading && "animate-pulse")}
        aria-hidden
      />
      <span className="truncate">{label}</span>
    </Link>
  );
}
