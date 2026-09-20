"use client";

import {
  Building2,
  FileSearch,
  Plus,
  Radar,
  Target as TargetIcon,
} from "lucide-react";
import Link from "next/link";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { ProgressBar } from "@/components/domain/progress";
import { StatCard } from "@/components/domain/stat-card";
import { CompanyStatusBadge, RunStatusBadge } from "@/components/domain/status";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { CardsSkeleton, EmptyState, ErrorState, TableSkeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { formatNumber, formatRelative } from "@/lib/format";

export default function DashboardPage() {
  const { data, error, isLoading, mutate } = useSWR("dashboard", api.dashboard, {
    // Keeps counters current while a discovery run is in flight.
    refreshInterval: 10_000,
  });

  const hasAnyData = (data?.targets_count ?? 0) > 0 || (data?.companies_count ?? 0) > 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Prospect discovery activity across all targets."
        actions={
          <Link href="/targets/new" className={buttonVariants()}>
            <Plus /> New target
          </Link>
        }
      />

      {error ? (
        <Card>
          <ErrorState message={error.message} onRetry={() => mutate()} />
        </Card>
      ) : (
        <>
          {isLoading ? (
            <CardsSkeleton />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Target sets"
                value={data?.targets_count ?? 0}
                icon={TargetIcon}
                hint="Saved search definitions"
              />
              <StatCard
                label="Companies found"
                value={data?.companies_count ?? 0}
                icon={Building2}
                hint={`${formatNumber(data?.sources_count ?? 0)} source links collected`}
              />
              <StatCard
                label="Research ready"
                value={data?.researched_count ?? 0}
                icon={FileSearch}
                hint={`${formatNumber(data?.pages_count ?? 0)} pages crawled`}
              />
              <StatCard
                label="Discovery runs"
                value={data?.runs_count ?? 0}
                icon={Radar}
                hint={summariseRuns(data?.runs_by_status)}
              />
            </div>
          )}

          {!isLoading && !hasAnyData ? (
            <Card className="mt-6">
              <EmptyState
                icon={TargetIcon}
                title="No data yet"
                description="Define a target — an industry, a location and any keywords — then run discovery to find companies from live web search."
                action={
                  <Link href="/targets/new" className={buttonVariants()}>
                    <Plus /> Create your first target
                  </Link>
                }
              />
            </Card>
          ) : (
            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Recent discovery runs</CardTitle>
                  <Link
                    href="/runs"
                    className="text-xs font-medium text-accent hover:underline"
                  >
                    View all
                  </Link>
                </CardHeader>
                {isLoading ? (
                  <TableSkeleton rows={3} columns={3} />
                ) : data && data.recent_runs.length > 0 ? (
                  <ul className="divide-y divide-border">
                    {data.recent_runs.map((run) => (
                      <li key={run.id}>
                        <Link
                          href={`/runs/${run.id}`}
                          className="block px-5 py-4 transition-colors hover:bg-surface-muted/50"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-foreground">
                                {run.industry}
                                {run.location ? ` / ${run.location}` : ""}
                              </p>
                              <p className="mt-0.5 truncate text-xs text-muted">
                                {run.target_name} · {formatRelative(run.created_at)}
                              </p>
                            </div>
                            <RunStatusBadge status={run.status} />
                          </div>
                          {run.status === "running" || run.status === "queued" ? (
                            <div className="mt-3">
                              <ProgressBar value={run.progress} />
                            </div>
                          ) : (
                            <p className="mt-2 text-xs text-muted">
                              {formatNumber(run.companies_found)}{" "}
                              {run.companies_found === 1 ? "company" : "companies"}
                            </p>
                          )}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    icon={Radar}
                    title="No discovery runs yet"
                    description="Run discovery on a target to populate this list."
                    action={
                      <Link
                        href="/targets"
                        className={buttonVariants({ variant: "secondary" })}
                      >
                        Go to targets
                      </Link>
                    }
                  />
                )}
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Latest prospects</CardTitle>
                  <Link
                    href="/companies"
                    className="text-xs font-medium text-accent hover:underline"
                  >
                    View all
                  </Link>
                </CardHeader>
                {isLoading ? (
                  <TableSkeleton rows={3} columns={3} />
                ) : data && data.recent_companies.length > 0 ? (
                  <ul className="divide-y divide-border">
                    {data.recent_companies.map((company) => (
                      <li key={company.id}>
                        <Link
                          href={`/companies/${company.id}`}
                          className="flex items-start justify-between gap-3 px-5 py-4 transition-colors hover:bg-surface-muted/50"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-foreground">
                              {company.name}
                            </p>
                            <p className="mt-0.5 truncate font-mono text-xs text-muted">
                              {company.canonical_domain}
                            </p>
                          </div>
                          <CompanyStatusBadge status={company.status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    icon={Building2}
                    title="No companies discovered yet"
                    description="Companies appear here once a discovery run completes."
                  />
                )}
              </Card>
            </div>
          )}
        </>
      )}
    </>
  );
}

function summariseRuns(byStatus: Record<string, number> | undefined): string {
  if (!byStatus) return "—";
  const parts = Object.entries(byStatus)
    .filter(([, count]) => count > 0)
    .map(([status, count]) => `${count} ${status}`);
  return parts.length ? parts.join(" · ") : "None yet";
}
