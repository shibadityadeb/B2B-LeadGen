"use client";

import { Microscope } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { ProgressBar } from "@/components/domain/progress";
import { ResearchStatusBadge } from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/format";

const PAGE_SIZE = 20;

export default function ResearchRunsPage() {
  const [page, setPage] = React.useState(1);
  const { data, error, isLoading, mutate } = useSWR(["research-runs", page], () =>
    api.listResearchRuns({ page, page_size: PAGE_SIZE }),
  );

  const hasActive = data?.items.some((run) =>
    ["queued", "researching", "analyzing"].includes(run.status),
  );

  React.useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(() => mutate(), 3000);
    return () => clearInterval(timer);
  }, [hasActive, mutate]);

  return (
    <>
      <PageHeader
        title="Research runs"
        description="Every company research run, with the evidence and hypotheses it produced."
      />

      <Card>
        {isLoading ? (
          <TableSkeleton columns={7} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={() => mutate()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Microscope}
            title="No research runs yet"
            description="Open a company and run research to populate this list."
            action={
              <Link href="/companies" className={buttonVariants()}>
                Go to companies
              </Link>
            }
          />
        ) : (
          <>
            <TableWrap>
              <Table className="min-w-[52rem]">
                <thead>
                  <tr>
                    <Th>Run</Th>
                    <Th>Company</Th>
                    <Th>Status</Th>
                    <Th>Started</Th>
                    <Th>Duration</Th>
                    <Th className="text-right">Evidence</Th>
                    <Th className="text-right">Signals</Th>
                    <Th className="text-right">Opportunities</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((run) => (
                    <Tr key={run.id}>
                      <Td>
                        <Link
                          href={`/research/${run.id}`}
                          className="font-medium text-foreground hover:text-accent"
                        >
                          #{run.id}
                        </Link>
                      </Td>
                      <Td>
                        <Link
                          href={`/companies/${run.company_id}`}
                          className="text-muted hover:text-accent"
                        >
                          {run.company_name ?? `Company ${run.company_id}`}
                        </Link>
                        <p className="font-mono text-xs text-subtle">{run.company_domain}</p>
                      </Td>
                      <Td>
                        <ResearchStatusBadge status={run.status} />
                        {["queued", "researching", "analyzing"].includes(run.status) ? (
                          <ProgressBar className="mt-2 w-28" value={run.progress} />
                        ) : null}
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {formatDateTime(run.started_at ?? run.created_at)}
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {formatDuration(run.started_at, run.completed_at)}
                      </Td>
                      <Td className="text-right tabular-nums text-muted">
                        {run.evidence_count}
                        {run.new_evidence_count > 0 ? (
                          <Badge tone="accent" className="ml-1.5">
                            +{run.new_evidence_count}
                          </Badge>
                        ) : null}
                      </Td>
                      <Td className="text-right tabular-nums text-muted">{run.signals_count}</Td>
                      <Td className="text-right tabular-nums text-muted">
                        {run.opportunities_count}
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
              label="research runs"
            />
          </>
        )}
      </Card>
    </>
  );
}
