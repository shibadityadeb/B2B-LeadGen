"use client";

import { Eye, Play, Plus, Target as TargetIcon, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { RunStatusBadge } from "@/components/domain/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, InlineError, TableSkeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/format";
import type { TargetListItem } from "@/lib/types";

export default function TargetsPage() {
  const router = useRouter();
  const { data, error, isLoading, mutate } = useSWR("targets", api.listTargets);

  const [pendingDelete, setPendingDelete] = React.useState<TargetListItem | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [runningId, setRunningId] = React.useState<number | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  async function runDiscovery(target: TargetListItem) {
    setActionError(null);
    setRunningId(target.id);
    try {
      const run = await api.startDiscovery(target.id);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not start the discovery run.",
      );
      setRunningId(null);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    setActionError(null);
    try {
      await api.deleteTarget(pendingDelete.id);
      setPendingDelete(null);
      await mutate();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not delete the target.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Targets"
        description="A target defines what to look for: an industry, a place, and optional keywords."
        actions={
          <Link href="/targets/new" className={buttonVariants()}>
            <Plus /> New target
          </Link>
        }
      />

      {actionError ? <InlineError className="mb-4" message={actionError} /> : null}

      <Card>
        {isLoading ? (
          <TableSkeleton columns={6} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={() => mutate()} />
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={TargetIcon}
            title="No targets yet"
            description="Create a target such as an industry and a city, then run discovery to find matching companies."
            action={
              <Link href="/targets/new" className={buttonVariants()}>
                <Plus /> New target
              </Link>
            }
          />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <Th>Target</Th>
                  <Th>Industry</Th>
                  <Th>Location</Th>
                  <Th>Created</Th>
                  <Th>Last run</Th>
                  <Th className="text-right">Companies</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {data.map((target) => (
                  <Tr key={target.id}>
                    <Td>
                      <Link
                        href={`/targets/${target.id}`}
                        className="font-medium text-foreground hover:text-accent"
                      >
                        {target.name}
                      </Link>
                      {target.keywords.length > 0 ? (
                        <p className="mt-0.5 truncate text-xs text-subtle">
                          {target.keywords.slice(0, 3).join(" · ")}
                          {target.keywords.length > 3 ? " …" : ""}
                        </p>
                      ) : null}
                    </Td>
                    <Td className="text-muted">{target.industry}</Td>
                    <Td className="text-muted">{target.location ?? "—"}</Td>
                    <Td className="whitespace-nowrap text-muted">
                      {formatDate(target.created_at)}
                    </Td>
                    <Td className="whitespace-nowrap">
                      {target.last_run_status && target.last_run_id ? (
                        <Link href={`/runs/${target.last_run_id}`} className="inline-flex flex-col gap-1">
                          <RunStatusBadge status={target.last_run_status} />
                          <span className="text-xs text-subtle">
                            {formatRelative(target.last_run_at)}
                          </span>
                        </Link>
                      ) : (
                        <span className="text-muted">Never</span>
                      )}
                    </Td>
                    <Td className="text-right tabular-nums text-muted">
                      {target.companies_count}
                    </Td>
                    <Td>
                      <div className="flex justify-end gap-1.5">
                        <Link
                          href={`/targets/${target.id}`}
                          className={buttonVariants({ variant: "ghost", size: "sm" })}
                          aria-label={`View ${target.name}`}
                        >
                          <Eye /> View
                        </Link>
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={runningId === target.id}
                          onClick={() => runDiscovery(target)}
                        >
                          <Play /> Run discovery
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`Delete ${target.name}`}
                          onClick={() => setPendingDelete(target)}
                        >
                          <Trash2 className="text-danger" />
                        </Button>
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>

      <ConfirmDialog
        open={pendingDelete !== null}
        loading={deleting}
        title={`Delete “${pendingDelete?.name ?? ""}”?`}
        description={
          <>
            This permanently deletes the target and its{" "}
            <Badge tone="neutral">discovery runs</Badge>, including their search queries and
            results. Companies already discovered are kept, but lose their link to this target.
            This cannot be undone.
          </>
        }
        onCancel={() => setPendingDelete(null)}
        onConfirm={confirmDelete}
      />
    </>
  );
}
