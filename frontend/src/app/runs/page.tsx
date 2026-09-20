"use client";

import { Radar } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { ProgressBar } from "@/components/domain/progress";
import { RunStatusBadge } from "@/components/domain/status";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/format";

const PAGE_SIZE = 20;

export default function RunsPage() {
  const [page, setPage] = React.useState(1);
  const { data, error, isLoading, mutate } = useSWR(["runs", page], () =>
    api.listRuns({ page, page_size: PAGE_SIZE }),
  );

  const hasActive = data?.items.some(
    (run) => run.status === "running" || run.status === "queued",
  );

  React.useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => mutate(), 3000);
    return () => clearInterval(timer);
  }, [hasActive, mutate]);

  return (
    <>
      <PageHeader
        title="Discovery runs"
        description="Every execution of the discovery pipeline, with the real queries and results it produced."
      />

      <Card>
        {isLoading ? (
          <TableSkeleton columns={6} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={() => mutate()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Radar}
            title="No discovery runs yet"
            description="Runs appear here once you start discovery on a target."
            action={
              <Link href="/targets" className={buttonVariants()}>
                Go to targets
              </Link>
            }
          />
        ) : (
          <>
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>Run</Th>
                    <Th>Target</Th>
                    <Th>Status</Th>
                    <Th>Started</Th>
                    <Th>Duration</Th>
                    <Th className="text-right">Results</Th>
                    <Th className="text-right">New companies</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((run) => (
                    <Tr key={run.id}>
                      <Td>
                        <Link
                          href={`/runs/${run.id}`}
                          className="font-medium text-foreground hover:text-accent"
                        >
                          #{run.id}
                        </Link>
                      </Td>
                      <Td>
                        <Link
                          href={`/targets/${run.target_id}`}
                          className="text-muted hover:text-accent"
                        >
                          {run.target_name ?? `Target ${run.target_id}`}
                        </Link>
                        <p className="text-xs text-subtle">
                          {run.target_industry}
                          {run.target_location ? ` / ${run.target_location}` : ""}
                        </p>
                      </Td>
                      <Td>
                        <RunStatusBadge status={run.status} />
                        {run.status === "running" || run.status === "queued" ? (
                          <ProgressBar className="mt-2 w-28" value={run.progress} />
                        ) : null}
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {formatDateTime(run.started_at ?? run.created_at)}
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {formatDuration(run.started_at, run.completed_at)}
                      </Td>
                      <Td className="text-right tabular-nums text-muted">{run.results_count}</Td>
                      <Td className="text-right tabular-nums text-muted">
                        {run.new_companies_count}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={data.total}
              onPageChange={setPage}
              label="runs"
            />
          </>
        )}
      </Card>
    </>
  );
}
