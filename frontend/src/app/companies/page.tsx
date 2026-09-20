"use client";

import { Building2, LayoutGrid, List, Microscope, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { CompanyStatusBadge } from "@/components/domain/status";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/ui/states";
import { RowLink, Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { InlineError } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { formatDate, humanize } from "@/lib/format";
import type { CompanyListItem } from "@/lib/types";

const PAGE_SIZE = 20;

export default function CompaniesPage() {
  return (
    <React.Suspense fallback={<CompaniesFallback />}>
      <CompaniesContent />
    </React.Suspense>
  );
}

function CompaniesFallback() {
  return (
    <>
      <PageHeader title="Companies" />
      <Card>
        <TableSkeleton columns={6} />
      </Card>
    </>
  );
}

function CompaniesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const targetId = searchParams.get("target_id");

  const [page, setPage] = React.useState(1);
  const [searchInput, setSearchInput] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [industry, setIndustry] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [discoveredAfter, setDiscoveredAfter] = React.useState("");
  const [view, setView] = React.useState<"table" | "cards">("table");
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = React.useState(false);
  const [bulkMessage, setBulkMessage] = React.useState<string | null>(null);
  const [bulkError, setBulkError] = React.useState<string | null>(null);

  // Debounce the free-text search so typing does not hammer the API.
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
    industry: industry || undefined,
    location: location || undefined,
    status: status || undefined,
    target_id: targetId ? Number(targetId) : undefined,
    discovered_after: discoveredAfter ? new Date(discoveredAfter).toISOString() : undefined,
  };

  const { data, error, isLoading, mutate } = useSWR(
    ["companies", JSON.stringify(filters)],
    () => api.listCompanies(filters),
    { keepPreviousData: true },
  );
  const options = useSWR("company-filters", api.companyFilters);

  function toggle(companyId: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(companyId)) next.delete(companyId);
      else next.add(companyId);
      return next;
    });
  }

  function toggleAllOnPage(items: CompanyListItem[]) {
    setSelected((current) => {
      const next = new Set(current);
      const allSelected = items.every((item) => next.has(item.id));
      for (const item of items) {
        if (allSelected) next.delete(item.id);
        else next.add(item.id);
      }
      return next;
    });
  }

  async function researchSelected() {
    setBulkBusy(true);
    setBulkError(null);
    setBulkMessage(null);
    try {
      const result = await api.bulkResearch([...selected]);
      const parts = [`${result.queued.length} queued for research`];
      if (result.skipped.length) parts.push(`${result.skipped.length} skipped`);
      setBulkMessage(parts.join(" · "));
      setSelected(new Set());
      await mutate();
    } catch (error) {
      setBulkError(
        error instanceof ApiError ? error.message : "Could not queue research.",
      );
    } finally {
      setBulkBusy(false);
    }
  }

  const filtersApplied =
    Boolean(search || industry || location || status || discoveredAfter || targetId);

  function clearFilters() {
    setSearchInput("");
    setSearch("");
    setIndustry("");
    setLocation("");
    setStatus("");
    setDiscoveredAfter("");
    setPage(1);
    if (targetId) router.push("/companies");
  }

  return (
    <>
      <PageHeader
        title="Companies"
        description="Every company discovered from search, with the sources that produced it."
        actions={
          <div className="flex gap-1 rounded-lg border border-border-strong p-0.5">
            <ViewToggle active={view === "table"} onClick={() => setView("table")} label="Table">
              <List className="size-4" />
            </ViewToggle>
            <ViewToggle active={view === "cards"} onClick={() => setView("cards")} label="Cards">
              <LayoutGrid className="size-4" />
            </ViewToggle>
          </div>
        }
      />

      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <div className="relative sm:col-span-2 xl:col-span-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-subtle" />
            <Input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Name or domain…"
              className="pl-8"
              aria-label="Search companies"
            />
          </div>
          <Select
            value={industry}
            onChange={(event) => {
              setIndustry(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by industry"
          >
            <option value="">All industries</option>
            {options.data?.industries.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
          <Select
            value={location}
            onChange={(event) => {
              setLocation(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by location"
          >
            <option value="">All locations</option>
            {options.data?.locations.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
          <Select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by research status"
          >
            <option value="">All statuses</option>
            {options.data?.statuses.map((value) => (
              <option key={value} value={value}>
                {humanize(value)}
              </option>
            ))}
          </Select>
          <Input
            type="date"
            value={discoveredAfter}
            onChange={(event) => {
              setDiscoveredAfter(event.target.value);
              setPage(1);
            }}
            aria-label="Discovered on or after"
          />
        </div>
        {filtersApplied ? (
          <div className="mt-3 flex items-center gap-2">
            {targetId ? (
              <span className="text-xs text-muted">Filtered to target #{targetId}</span>
            ) : null}
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <X /> Clear filters
            </Button>
          </div>
        ) : null}
      </Card>

      {bulkError ? <InlineError className="mb-4" message={bulkError} /> : null}
      {bulkMessage ? (
        <div
          role="status"
          className="mb-4 rounded-lg border border-accent-border bg-accent-soft px-3 py-2 text-sm text-accent"
        >
          {bulkMessage}
        </div>
      ) : null}

      {selected.size > 0 ? (
        <Card className="mb-4 flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <p className="text-sm text-foreground">
            <span className="font-medium">{selected.size}</span>{" "}
            {selected.size === 1 ? "company" : "companies"} selected
          </p>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Clear
            </Button>
            <Button size="sm" onClick={researchSelected} loading={bulkBusy}>
              <Microscope /> Research selected
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        {isLoading && !data ? (
          <TableSkeleton columns={6} />
        ) : error ? (
          <ErrorState message={error.message} onRetry={() => mutate()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={Building2}
            title={filtersApplied ? "No companies match these filters" : "No companies yet"}
            description={
              filtersApplied
                ? "Try widening or clearing the filters."
                : "Run discovery on a target to populate the company database."
            }
            action={
              filtersApplied ? (
                <Button variant="secondary" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : (
                <Link href="/targets" className={buttonVariants()}>
                  Go to targets
                </Link>
              )
            }
          />
        ) : view === "table" ? (
          <>
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th className="w-10">
                      <input
                        type="checkbox"
                        aria-label="Select all companies on this page"
                        className="size-4 cursor-pointer accent-[var(--accent)]"
                        checked={
                          data.items.length > 0 &&
                          data.items.every((item) => selected.has(item.id))
                        }
                        onChange={() => toggleAllOnPage(data.items)}
                      />
                    </Th>
                    <Th>Company</Th>
                    <Th>Industry</Th>
                    <Th>Location</Th>
                    <Th>Discovered</Th>
                    <Th>Research</Th>
                    <Th className="text-right">Sources</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((company) => (
                    <Tr key={company.id}>
                      <Td>
                        <input
                          type="checkbox"
                          aria-label={`Select ${company.name}`}
                          className="relative z-10 size-4 cursor-pointer accent-[var(--accent)]"
                          checked={selected.has(company.id)}
                          onChange={() => toggle(company.id)}
                        />
                      </Td>
                      <Td>
                        <RowLink href={`/companies/${company.id}`} className="group block min-w-0">
                          <span className="block truncate group-hover:text-accent">
                            {company.name}
                          </span>
                          <span className="block truncate font-mono text-xs font-normal text-subtle">
                            {company.canonical_domain}
                          </span>
                        </RowLink>
                      </Td>
                      <Td className="text-muted">{company.industry ?? "—"}</Td>
                      <Td className="text-muted">{company.location ?? "—"}</Td>
                      <Td className="whitespace-nowrap text-muted">
                        {formatDate(company.created_at)}
                      </Td>
                      <Td>
                        <CompanyStatusBadge status={company.status} />
                      </Td>
                      <Td className="text-right tabular-nums text-muted">
                        {company.sources_count}
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
              label="companies"
            />
          </>
        ) : (
          <>
            <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
              {data.items.map((company) => (
                <CompanyCard key={company.id} company={company} />
              ))}
            </div>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={data.total}
              onPageChange={setPage}
              label="companies"
            />
          </>
        )}
      </Card>
    </>
  );
}

function CompanyCard({ company }: { company: CompanyListItem }) {
  return (
    <Link
      href={`/companies/${company.id}`}
      className="group flex flex-col rounded-lg border border-border bg-surface p-4 transition-colors hover:border-accent-border hover:bg-accent-soft/40"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-sm font-medium text-foreground group-hover:text-accent">
          {company.name}
        </h3>
        <CompanyStatusBadge status={company.status} />
      </div>
      <p className="mt-1 truncate font-mono text-xs text-subtle">{company.canonical_domain}</p>
      {company.description ? (
        <p className="mt-2 line-clamp-2 text-xs text-muted">{company.description}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        {company.industry ? <span>{company.industry}</span> : null}
        {company.location ? <span>{company.location}</span> : null}
        <span>
          {company.sources_count} source{company.sources_count === 1 ? "" : "s"}
        </span>
      </div>
    </Link>
  );
}

function ViewToggle({
  active,
  onClick,
  label,
  children,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${label} view`}
      aria-pressed={active}
      className={
        active
          ? "rounded-md bg-accent-soft p-1.5 text-accent"
          : "rounded-md p-1.5 text-muted hover:bg-surface-muted"
      }
    >
      {children}
    </button>
  );
}
