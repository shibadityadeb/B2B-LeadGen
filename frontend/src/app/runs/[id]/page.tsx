"use client";

import { AlertTriangle, Building2, CheckCircle2, ExternalLink, RotateCw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { ProgressBar, stageLabel } from "@/components/domain/progress";
import { RunStatusBadge } from "@/components/domain/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber, humanize, truncate } from "@/lib/format";
import type { SearchResult } from "@/lib/types";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();

  const { data, error, isLoading, mutate } = useSWR(
    Number.isFinite(id) ? ["run", id] : null,
    () => api.getRun(id),
  );

  const [retrying, setRetrying] = React.useState(false);
  const [retryError, setRetryError] = React.useState<string | null>(null);
  const [resultFilter, setResultFilter] = React.useState<ResultFilter>("accepted");

  const active = data?.status === "running" || data?.status === "queued";

  // Poll only while the run is in flight; stop as soon as it settles.
  React.useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => mutate(), 2000);
    return () => clearInterval(timer);
  }, [active, mutate]);

  async function retry() {
    if (!data) return;
    setRetrying(true);
    setRetryError(null);
    try {
      const run = await api.startDiscovery(data.target_id);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setRetryError(err instanceof ApiError ? err.message : "Could not start a new run.");
      setRetrying(false);
    }
  }

  if (error) {
    return (
      <Card>
        <ErrorState title="Run not found" message={error.message} onRetry={() => mutate()} />
      </Card>
    );
  }

  const results = data?.results ?? [];
  // A result is only "rejected" once normalization has recorded a reason;
  // before that stage runs it is simply not evaluated yet.
  const accepted = results.filter((result) => result.accepted);
  const rejected = results.filter((result) => !result.accepted && result.rejection_reason);
  const pending = results.filter((result) => !result.accepted && !result.rejection_reason);
  const shown =
    resultFilter === "accepted" ? accepted : resultFilter === "rejected" ? rejected : pending;

  return (
    <>
      <PageHeader
        backHref="/runs"
        backLabel="Discovery runs"
        title={isLoading ? <Skeleton className="h-8 w-40" /> : `Discovery run #${id}`}
        description={
          data ? (
            <span className="flex flex-wrap items-center gap-2">
              <Link href={`/targets/${data.target_id}`} className="text-accent hover:underline">
                {data.target_name}
              </Link>
              <span className="text-subtle">·</span>
              <span>
                {data.target_industry}
                {data.target_location ? ` / ${data.target_location}` : ""}
              </span>
              {data.search_provider ? (
                <>
                  <span className="text-subtle">·</span>
                  <span>via {data.search_provider}</span>
                </>
              ) : null}
            </span>
          ) : undefined
        }
        actions={
          data?.status === "failed" ? (
            <Button onClick={retry} loading={retrying}>
              <RotateCw /> Retry run
            </Button>
          ) : undefined
        }
      />

      {retryError ? <InlineError className="mb-4" message={retryError} /> : null}

      {/* --- live status --- */}
      <Card className="mb-5">
        <CardContent className="space-y-4">
          {isLoading || !data ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <RunStatusBadge status={data.status} />
                  <span className="text-sm text-muted">
                    {stageLabel(data.stage, data.status)}
                  </span>
                </div>
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
                  <span>Started {formatDateTime(data.started_at ?? data.created_at)}</span>
                  <span>
                    {data.completed_at ? "Completed" : "Running for"}{" "}
                    {data.completed_at
                      ? formatDateTime(data.completed_at)
                      : formatDuration(data.started_at, null)}
                  </span>
                </div>
              </div>

              {active ? (
                <ProgressBar value={data.progress} />
              ) : data.status === "completed" ? (
                <p className="flex items-center gap-1.5 text-sm text-success">
                  <CheckCircle2 className="size-4" />
                  Completed in {formatDuration(data.started_at, data.completed_at)}
                </p>
              ) : null}

              {data.status === "failed" ? (
                <div className="rounded-lg border border-danger/30 bg-danger-soft p-4">
                  <p className="flex items-center gap-2 text-sm font-medium text-danger">
                    <AlertTriangle className="size-4" /> Discovery failed
                  </p>
                  <p className="mt-1.5 text-sm text-danger/90">
                    {data.error_message ?? "No further detail was recorded."}
                  </p>
                </div>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      {/* --- counters --- */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Metric label="Queries" value={data?.queries_count} loading={isLoading} />
        <Metric label="Search results" value={data?.results_count} loading={isLoading} />
        <Metric label="Unique domains" value={data?.unique_domains_count} loading={isLoading} />
        <Metric label="New companies" value={data?.new_companies_count} loading={isLoading} />
        <Metric label="Duplicates" value={data?.duplicate_companies_count} loading={isLoading} />
        <Metric
          label="Rejected results"
          value={data?.rejected_results_count}
          loading={isLoading}
        />
      </div>

      {data && data.failed_queries_count > 0 ? (
        <InlineError
          className="mb-5"
          message={`${data.failed_queries_count} of ${data.queries_count} queries failed. The run continued with the remaining queries.`}
        />
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        {/* --- queries --- */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Search queries</CardTitle>
            {data ? <Badge>{data.queries.length}</Badge> : null}
          </CardHeader>
          {isLoading ? (
            <CardContent className="space-y-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-8 w-full" />
              ))}
            </CardContent>
          ) : data && data.queries.length > 0 ? (
            <ul className="divide-y divide-border">
              {data.queries.map((query) => (
                <li key={query.id} className="px-5 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="min-w-0 break-words font-mono text-xs text-foreground">
                      {query.query}
                    </p>
                    <Badge
                      tone={
                        query.status === "failed"
                          ? "danger"
                          : query.results_count > 0
                            ? "success"
                            : "neutral"
                      }
                    >
                      {query.status === "failed" ? "Failed" : `${query.results_count}`}
                    </Badge>
                  </div>
                  {query.error_message ? (
                    <p className="mt-1 text-xs text-danger">{query.error_message}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No queries yet"
              description="Queries appear as soon as the run generates them."
            />
          )}
        </Card>

        {/* --- results --- */}
        <Card>
          <CardHeader>
            <CardTitle>Search results</CardTitle>
            <div className="flex gap-1.5">
              <FilterTab
                active={resultFilter === "accepted"}
                onClick={() => setResultFilter("accepted")}
              >
                Accepted ({accepted.length})
              </FilterTab>
              <FilterTab
                active={resultFilter === "rejected"}
                onClick={() => setResultFilter("rejected")}
              >
                Rejected ({rejected.length})
              </FilterTab>
              {pending.length > 0 ? (
                <FilterTab
                  active={resultFilter === "pending"}
                  onClick={() => setResultFilter("pending")}
                >
                  Not yet evaluated ({pending.length})
                </FilterTab>
              ) : null}
            </div>
          </CardHeader>
          {isLoading ? (
            <CardContent className="space-y-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </CardContent>
          ) : shown.length > 0 ? (
            <TableWrap>
              <Table className="min-w-[34rem]">
                <thead>
                  <tr>
                    <Th>Result</Th>
                    <Th>Domain</Th>
                    <Th>{resultFilter === "accepted" ? "Engine" : "Reason"}</Th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((result) => (
                    <ResultRow key={result.id} result={result} />
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : (
            <EmptyState
              title={EMPTY_TITLES[resultFilter]}
              description={
                active
                  ? "Results are normalized once every search query has finished."
                  : EMPTY_DESCRIPTIONS[resultFilter]
              }
            />
          )}
          {data && data.results_count > results.length ? (
            <div className="border-t border-border px-5 py-3 text-xs text-muted">
              Showing the first {results.length} of {formatNumber(data.results_count)} stored
              results.
            </div>
          ) : null}
        </Card>
      </div>

      {data && data.new_companies_count + data.duplicate_companies_count > 0 ? (
        <div className="mt-5">
          <Link
            href={`/companies?target_id=${data.target_id}`}
            className={buttonVariants({ variant: "secondary" })}
          >
            <Building2 /> View companies from this target
          </Link>
        </div>
      ) : null}
    </>
  );
}

type ResultFilter = "accepted" | "rejected" | "pending";

const EMPTY_TITLES: Record<ResultFilter, string> = {
  accepted: "No accepted results",
  rejected: "No rejected results",
  pending: "Nothing awaiting evaluation",
};

const EMPTY_DESCRIPTIONS: Record<ResultFilter, string> = {
  accepted: "No search result resolved to a usable company website in this run.",
  rejected: "Every result in this run resolved to a company website.",
  pending: "All results have been evaluated.",
};

function ResultRow({ result }: { result: SearchResult }) {
  return (
    <Tr>
      <Td>
        <a
          href={result.url}
          target="_blank"
          rel="noreferrer noopener"
          className="group inline-flex max-w-md items-start gap-1.5"
        >
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-foreground group-hover:text-accent">
              {result.title ?? result.url}
            </span>
            <span className="block truncate text-xs text-subtle">{truncate(result.url, 80)}</span>
          </span>
          <ExternalLink className="mt-0.5 size-3.5 shrink-0 text-subtle" />
        </a>
      </Td>
      <Td className="font-mono text-xs text-muted">{result.extracted_domain ?? "—"}</Td>
      <Td>
        {result.accepted ? (
          <span className="text-xs text-muted">{result.source_engine ?? "—"}</span>
        ) : result.rejection_reason ? (
          <Badge tone="warning">{humanize(result.rejection_reason)}</Badge>
        ) : (
          <Badge tone="neutral">Pending</Badge>
        )}
      </Td>
    </Tr>
  );
}

function FilterTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={
        active
          ? "rounded-md bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent"
          : "rounded-md px-2.5 py-1 text-xs font-medium text-muted hover:bg-surface-muted"
      }
    >
      {children}
    </button>
  );
}

function Metric({
  label,
  value,
  loading,
}: {
  label: string;
  value: number | undefined;
  loading?: boolean;
}) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs text-subtle">{label}</p>
      {loading ? (
        <Skeleton className="mt-1.5 h-6 w-10" />
      ) : (
        <p className="mt-0.5 text-xl font-semibold tabular-nums text-foreground">
          {formatNumber(value ?? 0)}
        </p>
      )}
    </Card>
  );
}
