"use client";

import { Building2, Play, Radar, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { ProgressBar } from "@/components/domain/progress";
import { RunStatusBadge } from "@/components/domain/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, InlineError, Skeleton, TableSkeleton } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatNumber, formatRelative, humanize } from "@/lib/format";

export default function TargetDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();

  const target = useSWR(Number.isFinite(id) ? ["target", id] : null, () => api.getTarget(id));
  const runs = useSWR(Number.isFinite(id) ? ["target-runs", id] : null, () =>
    api.listRuns({ target_id: id, page_size: 10 }),
  );
  const companies = useSWR(Number.isFinite(id) ? ["target-companies", id] : null, () =>
    api.listCompanies({ target_id: id, page_size: 1 }),
  );

  const [starting, setStarting] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Poll while a run for this target is still in flight.
  const hasActiveRun = runs.data?.items.some(
    (run) => run.status === "queued" || run.status === "running",
  );
  React.useEffect(() => {
    if (!hasActiveRun) return;
    const timer = setInterval(() => {
      runs.mutate();
      companies.mutate();
    }, 3000);
    return () => clearInterval(timer);
  }, [hasActiveRun, runs, companies]);

  async function startDiscovery() {
    setStarting(true);
    setError(null);
    try {
      const run = await api.startDiscovery(id);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the discovery run.");
      setStarting(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await api.deleteTarget(id);
      router.push("/targets");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the target.");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (target.error) {
    return (
      <Card>
        <ErrorState
          title="Target not found"
          message={target.error.message}
          onRetry={() => target.mutate()}
        />
      </Card>
    );
  }

  return (
    <>
      <PageHeader
        backHref="/targets"
        backLabel="Targets"
        title={target.data?.name ?? <Skeleton className="h-8 w-64" />}
        description={
          target.data
            ? `${target.data.industry}${target.data.location ? ` · ${target.data.location}` : ""}${
                target.data.country ? `, ${target.data.country}` : ""
              }`
            : undefined
        }
        actions={
          <>
            <Button onClick={startDiscovery} loading={starting} disabled={!target.data}>
              <Play /> Run discovery
            </Button>
            <Button variant="dangerGhost" onClick={() => setConfirmDelete(true)}>
              <Trash2 /> Delete
            </Button>
          </>
        }
      />

      {error ? <InlineError className="mb-4" message={error} /> : null}

      <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {target.isLoading || !target.data ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-5 w-full" />
                ))}
              </div>
            ) : (
              <>
                <Detail label="Industry" value={target.data.industry} />
                <Detail label="Location" value={target.data.location ?? "Any"} />
                <Detail label="Country / region" value={target.data.country ?? "Any"} />
                <Detail
                  label="Company size"
                  value={target.data.company_size ? humanize(target.data.company_size) : "Any"}
                />
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-subtle">
                    Keywords
                  </p>
                  {target.data.keywords.length > 0 ? (
                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                      {target.data.keywords.map((keyword) => (
                        <li key={keyword}>
                          <Badge>{keyword}</Badge>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-sm text-muted">None</p>
                  )}
                </div>
                {target.data.search_context ? (
                  <Detail label="Search context" value={target.data.search_context} />
                ) : null}
                <Detail label="Created" value={formatDateTime(target.data.created_at)} />
                <Detail
                  label="Companies discovered"
                  value={formatNumber(companies.data?.total ?? 0)}
                />
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Discovery runs</CardTitle>
            <Link href="/runs" className="text-xs font-medium text-accent hover:underline">
              All runs
            </Link>
          </CardHeader>
          {runs.isLoading ? (
            <TableSkeleton rows={3} columns={3} />
          ) : runs.error ? (
            <ErrorState message={runs.error.message} onRetry={() => runs.mutate()} />
          ) : runs.data && runs.data.items.length > 0 ? (
            <ul className="divide-y divide-border">
              {runs.data.items.map((run) => (
                <li key={run.id}>
                  <Link
                    href={`/runs/${run.id}`}
                    className="block px-5 py-4 transition-colors hover:bg-surface-muted/50"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium text-foreground">Run #{run.id}</span>
                      <RunStatusBadge status={run.status} />
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      {formatRelative(run.created_at)} · {run.queries_count} queries ·{" "}
                      {run.results_count} results · {run.new_companies_count} new companies
                    </p>
                    {run.status === "running" || run.status === "queued" ? (
                      <ProgressBar className="mt-3" value={run.progress} />
                    ) : null}
                    {run.status === "failed" && run.error_message ? (
                      <p className="mt-2 text-xs text-danger">{run.error_message}</p>
                    ) : null}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={Radar}
              title="No discovery runs for this target"
              description="Run discovery to search the web and collect companies matching this definition."
              action={
                <Button onClick={startDiscovery} loading={starting}>
                  <Play /> Run discovery
                </Button>
              }
            />
          )}
          {companies.data && companies.data.total > 0 ? (
            <div className="border-t border-border px-5 py-3">
              <Link
                href={`/companies?target_id=${id}`}
                className={buttonVariants({ variant: "secondary", size: "sm" })}
              >
                <Building2 /> View {formatNumber(companies.data.total)} companies
              </Link>
            </div>
          ) : null}
        </Card>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        loading={deleting}
        title={`Delete “${target.data?.name ?? ""}”?`}
        description="This permanently deletes the target and all of its discovery runs, queries and search results. Discovered companies are kept. This cannot be undone."
        onCancel={() => setConfirmDelete(false)}
        onConfirm={remove}
      />
    </>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-subtle">{label}</p>
      <p className="mt-0.5 text-sm text-foreground">{value}</p>
    </div>
  );
}
