"use client";

import { AlertTriangle, ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { ProgressBar } from "@/components/domain/progress";
import { ResearchStatusBadge } from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber, humanize, truncate } from "@/lib/format";

export default function ResearchRunDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const { data, error, isLoading, mutate } = useSWR(
    Number.isFinite(id) ? ["research-run", id] : null,
    () => api.getResearchRun(id),
  );

  const active =
    data && ["queued", "researching", "analyzing"].includes(data.status);

  React.useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => mutate(), 2500);
    return () => clearInterval(timer);
  }, [active, mutate]);

  if (error) {
    return (
      <Card>
        <ErrorState title="Research run not found" message={error.message} onRetry={() => mutate()} />
      </Card>
    );
  }

  // LLM bookkeeping is recorded in `errors` alongside real failures; split it.
  const llmStats = data?.errors.find((item) => item.stage === "llm_extraction")?.stats;
  const uncertainties = (data?.errors ?? []).filter((item) => item.stage === "llm_uncertainty");
  const failures = (data?.errors ?? []).filter(
    (item) => item.stage && !item.stage.startsWith("llm_"),
  );

  return (
    <>
      <PageHeader
        backHref="/research"
        backLabel="Research runs"
        title={isLoading ? <Skeleton className="h-8 w-44" /> : `Research run #${id}`}
        description={
          data ? (
            <span className="flex flex-wrap items-center gap-2">
              <Link href={`/companies/${data.company_id}`} className="text-accent hover:underline">
                {data.company_name}
              </Link>
              <span className="text-subtle">·</span>
              <span className="font-mono text-xs">{data.company_domain}</span>
              {data.llm_used ? (
                <>
                  <span className="text-subtle">·</span>
                  <span>LLM-assisted ({data.llm_provider})</span>
                </>
              ) : (
                <>
                  <span className="text-subtle">·</span>
                  <span>deterministic extraction</span>
                </>
              )}
            </span>
          ) : undefined
        }
      />

      <Card className="mb-5">
        <CardContent className="space-y-3">
          {!data ? (
            <Skeleton className="h-14 w-full" />
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <ResearchStatusBadge status={data.status} />
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
                  <span>Started {formatDateTime(data.started_at ?? data.created_at)}</span>
                  <span>Duration {formatDuration(data.started_at, data.completed_at)}</span>
                </div>
              </div>
              {active ? <ProgressBar value={data.progress} /> : null}
              {data.status === "failed" ? (
                <div className="rounded-lg border border-danger/30 bg-danger-soft p-4">
                  <p className="flex items-center gap-2 text-sm font-medium text-danger">
                    <AlertTriangle className="size-4" /> Research failed
                  </p>
                  <p className="mt-1.5 text-sm text-danger/90">{data.error_message}</p>
                </div>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <Metric label="Sources found" value={data?.sources_discovered} loading={isLoading} />
        <Metric label="Sources retrieved" value={data?.sources_retrieved} loading={isLoading} />
        <Metric label="Evidence" value={data?.evidence_count} loading={isLoading} />
        <Metric label="New evidence" value={data?.new_evidence_count} loading={isLoading} />
        <Metric label="Signals" value={data?.signals_count} loading={isLoading} />
        <Metric label="Opportunities" value={data?.opportunities_count} loading={isLoading} />
      </div>

      {llmStats ? (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>Language model contribution</CardTitle>
            <span className="text-xs text-subtle">
              Claims are discarded unless their excerpt appears in a retrieved source
            </span>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Badge tone="neutral">{llmStats.returned ?? 0} returned</Badge>
            <Badge tone="success">{llmStats.accepted ?? 0} verified</Badge>
            <Badge tone="warning">{llmStats.rejected_unverified ?? 0} not in source</Badge>
            <Badge tone="warning">{llmStats.rejected_bad_type ?? 0} invalid type</Badge>
          </CardContent>
        </Card>
      ) : null}

      {(failures.length > 0 || uncertainties.length > 0) && data ? (
        <Card className="mb-5 border-warning/40 bg-warning-soft/40">
          <CardHeader>
            <CardTitle>Notes from this run</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1.5 text-sm text-muted">
              {failures.map((item, index) => (
                <li key={`f-${index}`}>
                  <span className="font-medium text-foreground">{humanize(item.stage)}:</span>{" "}
                  {item.message}
                </li>
              ))}
              {uncertainties.map((item, index) => (
                <li key={`u-${index}`}>
                  <span className="font-medium text-foreground">Uncertainty:</span> {item.message}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <Card>
          <CardHeader>
            <CardTitle>Sources collected in this run</CardTitle>
            {data ? <Badge>{data.sources.length}</Badge> : null}
          </CardHeader>
          {isLoading ? (
            <CardContent>
              <Skeleton className="h-32 w-full" />
            </CardContent>
          ) : (data?.sources.length ?? 0) === 0 ? (
            <EmptyState title="No sources recorded for this run" />
          ) : (
            <TableWrap>
              <Table className="min-w-[36rem]">
                <thead>
                  <tr>
                    <Th>Source</Th>
                    <Th>Type</Th>
                    <Th>Status</Th>
                    <Th className="text-right">Chars</Th>
                  </tr>
                </thead>
                <tbody>
                  {data?.sources.map((source) => (
                    <Tr key={source.id}>
                      <Td>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="group flex max-w-sm items-start gap-1.5"
                        >
                          <span className="min-w-0">
                            <span className="block truncate text-sm text-foreground group-hover:text-accent">
                              {source.title ?? source.url}
                            </span>
                            <span className="block truncate text-xs text-subtle">
                              {truncate(source.url, 64)}
                            </span>
                          </span>
                          <ExternalLink className="mt-0.5 size-3 shrink-0 text-subtle" />
                        </a>
                      </Td>
                      <Td>
                        <Badge tone="neutral">{humanize(source.source_type)}</Badge>
                      </Td>
                      <Td>
                        <Badge
                          tone={
                            source.retrieval_status === "retrieved"
                              ? "success"
                              : source.retrieval_status === "skipped"
                                ? "warning"
                                : "danger"
                          }
                          title={source.error_message ?? undefined}
                        >
                          {humanize(source.retrieval_status)}
                        </Badge>
                      </Td>
                      <Td className="text-right tabular-nums text-muted">
                        {source.content_length > 0 ? formatNumber(source.content_length) : "—"}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Brief from this run</CardTitle>
          </CardHeader>
          <CardContent>
            {data?.brief_markdown ? (
              <pre className="max-h-[34rem] overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-3 text-xs leading-relaxed text-foreground">
                {data.brief_markdown}
              </pre>
            ) : (
              <EmptyState icon={FileText} title="No brief for this run" />
            )}
          </CardContent>
        </Card>
      </div>
    </>
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
