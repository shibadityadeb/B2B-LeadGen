"use client";

import { Clock, Mail, Search, Send, Users, X } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { StatCard } from "@/components/domain/stat-card";
import {
  OutcomeBadge,
  OutreachStatusBadge,
  ValidationBadge,
} from "@/components/outreach/outreach-badges";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { CardsSkeleton, EmptyState, ErrorState, TableSkeleton } from "@/components/ui/states";
import { RowLink, Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { OutcomeStatus, OutreachStatus, ValidationResult } from "@/lib/types";

const PAGE_SIZE = 20;

const STATUSES: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "review", label: "Awaiting review" },
  { value: "approved", label: "Approved" },
  { value: "gmail_draft_created", label: "Gmail draft created" },
  { value: "sent", label: "Marked sent" },
  { value: "follow_up_due", label: "Follow-up due" },
  { value: "completed", label: "Completed" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled" },
];

export default function OutreachWorkspacePage() {
  const [page, setPage] = React.useState(1);
  const [searchInput, setSearchInput] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [followUpDue, setFollowUpDue] = React.useState(false);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const filters = {
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    status: status || undefined,
    follow_up_due: followUpDue || undefined,
  };

  const list = useSWR(["outreach", JSON.stringify(filters)], () => api.listOutreach(filters), {
    keepPreviousData: true,
  });
  const analytics = useSWR("outreach-analytics", api.outreachAnalytics, {
    refreshInterval: 30_000,
  });

  const filtersApplied = Boolean(search || status || followUpDue);

  function clearFilters() {
    setSearchInput("");
    setSearch("");
    setStatus("");
    setFollowUpDue(false);
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title="Outreach"
        description="Every prepared message, its approval state and what happened next. Nothing is ever sent automatically."
        actions={
          <Link href="/campaigns" className={buttonVariants({ variant: "secondary" })}>
            Campaigns
          </Link>
        }
      />

      {analytics.isLoading ? (
        <CardsSkeleton />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Awaiting review"
            value={analytics.data?.awaiting_review ?? 0}
            icon={Users}
            hint="Generated, not yet approved by a human"
          />
          <StatCard
            label="Gmail drafts"
            value={analytics.data?.gmail_drafts ?? 0}
            icon={Mail}
            hint="Created in your mailbox — not sent"
          />
          <StatCard
            label="Marked sent"
            value={analytics.data?.marked_sent ?? 0}
            icon={Send}
            hint="Recorded by a person after sending"
          />
          <StatCard
            label="Follow-ups due"
            value={analytics.data?.follow_ups_due ?? 0}
            icon={Clock}
            hint={`${formatNumber(analytics.data?.replies ?? 0)} replies recorded`}
          />
        </div>
      )}

      <Card className="mb-5 mt-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="relative sm:col-span-2 xl:col-span-2">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-subtle" />
            <Input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Company, recipient or email…"
              className="pl-8"
              aria-label="Search outreach"
            />
          </div>
          <Select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by status"
          >
            {STATUSES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={followUpDue}
              onChange={(event) => {
                setFollowUpDue(event.target.checked);
                setPage(1);
              }}
              className="size-4 cursor-pointer accent-[var(--accent)]"
            />
            Follow-up due only
          </label>
        </div>
        {filtersApplied ? (
          <Button variant="ghost" size="sm" className="mt-3" onClick={clearFilters}>
            <X /> Clear filters
          </Button>
        ) : null}
      </Card>

      <Card>
        {list.isLoading && !list.data ? (
          <TableSkeleton columns={7} />
        ) : list.error ? (
          <ErrorState message={list.error.message} onRetry={() => list.mutate()} />
        ) : !list.data || list.data.items.length === 0 ? (
          <EmptyState
            icon={Mail}
            title={filtersApplied ? "No outreach matches these filters" : "No outreach yet"}
            description={
              filtersApplied
                ? "Try widening or clearing the filters."
                : "Open a company opportunity and choose Create outreach to prepare a message."
            }
            action={
              filtersApplied ? (
                <Button variant="secondary" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : (
                <Link href="/companies" className={buttonVariants()}>
                  Go to companies
                </Link>
              )
            }
          />
        ) : (
          <>
            <TableWrap>
              <Table className="min-w-[60rem]">
                <thead>
                  <tr>
                    <Th>Company</Th>
                    <Th>Recipient</Th>
                    <Th>Opportunity</Th>
                    <Th>Status</Th>
                    <Th>Checks</Th>
                    <Th>Created</Th>
                    <Th>Sent</Th>
                    <Th>Next follow-up</Th>
                    <Th>Outcome</Th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((item) => {
                    const validation = item.validation as ValidationResult;
                    return (
                      <Tr key={item.id}>
                        <Td>
                          <RowLink
                            href={`/outreach/${item.id}`}
                            className="group block min-w-0 max-w-[14rem]"
                          >
                            <span className="block truncate group-hover:text-accent">
                              {item.company_name}
                            </span>
                            <span className="block truncate font-mono text-xs font-normal text-subtle">
                              {item.company_domain}
                            </span>
                          </RowLink>
                        </Td>
                        <Td>
                          <span className="block max-w-[12rem] truncate text-sm text-foreground">
                            {item.to_name ?? (
                              <span className="italic text-muted">Not published</span>
                            )}
                          </span>
                          <span className="block max-w-[12rem] truncate text-xs text-subtle">
                            {item.to_email ?? item.recipient_role ?? "—"}
                          </span>
                        </Td>
                        <Td className="max-w-[12rem] truncate text-muted">
                          {item.capability_name ?? item.opportunity_title ?? "—"}
                        </Td>
                        <Td>
                          <OutreachStatusBadge status={item.status as OutreachStatus} />
                          {item.follow_up_number > 0 ? (
                            <p className="mt-1 text-xs text-subtle">
                              Follow-up #{item.follow_up_number}
                            </p>
                          ) : null}
                        </Td>
                        <Td>
                          {validation?.errors ? (
                            <ValidationBadge
                              valid={validation.valid}
                              errors={validation.errors.length}
                              warnings={validation.warnings.length}
                            />
                          ) : (
                            "—"
                          )}
                        </Td>
                        <Td className="whitespace-nowrap text-muted">
                          {formatDate(item.created_at)}
                        </Td>
                        <Td className="whitespace-nowrap text-muted">
                          {item.sent_at ? formatDate(item.sent_at) : "—"}
                        </Td>
                        <Td className="whitespace-nowrap">
                          {item.next_follow_up_at ? (
                            <span className={item.follow_up_due ? "text-warning" : "text-muted"}>
                              {formatDate(item.next_follow_up_at)}
                            </span>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </Td>
                        <Td>
                          {item.outcome_status ? (
                            <OutcomeBadge status={item.outcome_status as OutcomeStatus} />
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </Td>
                      </Tr>
                    );
                  })}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={list.data.total}
              onPageChange={setPage}
              label="outreach"
            />
          </>
        )}
      </Card>
    </>
  );
}
