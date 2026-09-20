"use client";

import {
  AlertTriangle,
  ExternalLink,
  FileSearch,
  Globe,
  Link2,
  Loader2,
  Mail,
  Phone,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { CompanyStatusBadge, PageTypeBadge } from "@/components/domain/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatNumber, humanize, truncate } from "@/lib/format";

export default function CompanyDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const { data, error, isLoading, mutate } = useSWR(
    Number.isFinite(id) ? ["company", id] : null,
    () => api.getCompany(id),
  );

  const [starting, setStarting] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);

  const researching = data?.status === "researching";

  // Poll while the crawl job runs.
  React.useEffect(() => {
    if (!researching) return;
    const timer = setInterval(() => mutate(), 2500);
    return () => clearInterval(timer);
  }, [researching, mutate]);

  async function research() {
    setStarting(true);
    setActionError(null);
    try {
      await api.crawlCompany(id);
      await mutate();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not start the crawl.");
    } finally {
      setStarting(false);
    }
  }

  if (error) {
    return (
      <Card>
        <ErrorState title="Company not found" message={error.message} onRetry={() => mutate()} />
      </Card>
    );
  }

  return (
    <>
      <PageHeader
        backHref="/companies"
        backLabel="Companies"
        title={data?.name ?? <Skeleton className="h-8 w-64" />}
        description={
          data ? (
            <a
              href={data.website_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 font-mono text-sm text-accent hover:underline"
            >
              {data.canonical_domain}
              <ExternalLink className="size-3.5" />
            </a>
          ) : undefined
        }
        actions={
          <Button onClick={research} loading={starting || researching} disabled={!data}>
            <FileSearch />
            {researching
              ? "Researching…"
              : data?.last_researched_at
                ? "Re-run website research"
                : "Research website"}
          </Button>
        }
      />

      {actionError ? <InlineError className="mb-4" message={actionError} /> : null}

      {researching ? (
        <Card className="mb-5 border-accent-border bg-accent-soft/50">
          <CardContent className="flex items-center gap-3">
            <Loader2 className="size-4 animate-spin text-accent" />
            <div>
              <p className="text-sm font-medium text-foreground">Crawling the website…</p>
              <p className="text-xs text-muted">
                Fetching the homepage and a few standard pages, respecting robots.txt and rate
                limits. This page updates automatically.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {data?.status === "research_failed" && data.crawl_error ? (
        <Card className="mb-5 border-danger/30 bg-danger-soft">
          <CardContent>
            <p className="flex items-center gap-2 text-sm font-medium text-danger">
              <AlertTriangle className="size-4" /> Website research failed
            </p>
            <p className="mt-1.5 text-sm text-danger/90">{data.crawl_error}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={research} loading={starting}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Company</CardTitle>
              {data ? <CompanyStatusBadge status={data.status} /> : null}
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading || !data ? (
                <div className="space-y-3">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-5 w-full" />
                  ))}
                </div>
              ) : (
                <>
                  <Detail label="Website" value={
                    <a
                      href={data.website_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="break-all text-accent hover:underline"
                    >
                      {data.website_url}
                    </a>
                  } />
                  <Detail label="Canonical domain" value={
                    <span className="font-mono">{data.canonical_domain}</span>
                  } />
                  <Detail label="Industry" value={data.industry ?? "Unknown"} />
                  <Detail label="Location" value={data.location ?? "Unknown"} />
                  <Detail label="Country" value={data.country ?? "Unknown"} />
                  <Detail
                    label="Company size"
                    value={data.company_size ? humanize(data.company_size) : "Unknown"}
                  />
                  <Detail label="Discovered" value={formatDateTime(data.created_at)} />
                  <Detail
                    label="Last researched"
                    value={
                      data.last_researched_at ? formatDateTime(data.last_researched_at) : "Never"
                    }
                  />
                  {data.first_discovery_run_id ? (
                    <Detail
                      label="First found by"
                      value={
                        <Link
                          href={`/runs/${data.first_discovery_run_id}`}
                          className="text-accent hover:underline"
                        >
                          Discovery run #{data.first_discovery_run_id}
                        </Link>
                      }
                    />
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>

          {data && (data.summary.emails.length > 0 || data.summary.phones.length > 0) ? (
            <Card>
              <CardHeader>
                <CardTitle>Contact details found on the website</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {data.summary.emails.map((email) => (
                  <p key={email} className="flex items-center gap-2 text-sm text-foreground">
                    <Mail className="size-3.5 text-subtle" />
                    <a href={`mailto:${email}`} className="break-all hover:text-accent">
                      {email}
                    </a>
                  </p>
                ))}
                {data.summary.phones.map((phone) => (
                  <p key={phone} className="flex items-center gap-2 text-sm text-foreground">
                    <Phone className="size-3.5 text-subtle" />
                    {phone}
                  </p>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-5">
          {/* --- deterministic summary --- */}
          <Card>
            <CardHeader>
              <CardTitle>Website information</CardTitle>
              <span className="text-xs text-subtle">Extracted, not generated</span>
            </CardHeader>
            <CardContent>
              {isLoading || !data ? (
                <Skeleton className="h-20 w-full" />
              ) : data.summary.facts.length > 0 ? (
                <>
                  <ul className="space-y-1.5">
                    {data.summary.facts.map((fact) => (
                      <li key={fact} className="flex gap-2 text-sm text-foreground">
                        <span className="mt-1.5 size-1 shrink-0 rounded-full bg-subtle" />
                        {fact}
                      </li>
                    ))}
                  </ul>
                  {data.description ? (
                    <p className="mt-4 border-t border-border pt-4 text-sm text-muted">
                      <span className="font-medium text-foreground">
                        From the homepage:
                      </span>{" "}
                      “{data.description}”
                    </p>
                  ) : null}
                  <p className="mt-4 text-xs text-subtle">
                    {formatNumber(data.summary.total_content_chars)} characters of page text
                    stored. Interpretation of this content is a later phase.
                  </p>
                </>
              ) : (
                <EmptyState
                  icon={Globe}
                  title="No website information yet"
                  description="Run website research to crawl the homepage and a few standard pages."
                  action={
                    <Button onClick={research} loading={starting}>
                      <FileSearch /> Research website
                    </Button>
                  }
                />
              )}
            </CardContent>
          </Card>

          {/* --- crawled pages --- */}
          <Card>
            <CardHeader>
              <CardTitle>Discovered pages</CardTitle>
              {data ? <Badge>{data.pages.length}</Badge> : null}
            </CardHeader>
            {isLoading ? (
              <CardContent>
                <Skeleton className="h-24 w-full" />
              </CardContent>
            ) : data && data.pages.length > 0 ? (
              <TableWrap>
                <Table className="min-w-[36rem]">
                  <thead>
                    <tr>
                      <Th>Page</Th>
                      <Th>Type</Th>
                      <Th>Status</Th>
                      <Th className="text-right">Content</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.pages.map((page) => (
                      <Tr key={page.id}>
                        <Td>
                          <a
                            href={page.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="group block min-w-0 max-w-sm"
                          >
                            <span className="block truncate text-sm text-foreground group-hover:text-accent">
                              {page.title ?? page.url}
                            </span>
                            <span className="block truncate text-xs text-subtle">
                              {truncate(page.url, 70)}
                            </span>
                          </a>
                        </Td>
                        <Td>
                          <PageTypeBadge type={page.page_type} />
                        </Td>
                        <Td>
                          <Badge
                            tone={
                              page.status === "success"
                                ? "success"
                                : page.status === "skipped"
                                  ? "warning"
                                  : "danger"
                            }
                          >
                            {humanize(page.status)}
                          </Badge>
                          {page.error_message ? (
                            <p className="mt-1 max-w-xs text-xs text-muted">
                              {page.error_message}
                            </p>
                          ) : null}
                        </Td>
                        <Td className="text-right tabular-nums text-muted">
                          {page.content_length > 0
                            ? `${formatNumber(page.content_length)} chars`
                            : "—"}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            ) : (
              <EmptyState
                icon={Globe}
                title="No pages crawled yet"
                description="The initial crawl fetches the homepage and a small set of standard pages such as About, Products, Contact and News."
              />
            )}
          </Card>

          {/* --- evidence --- */}
          <Card>
            <CardHeader>
              <CardTitle>Sources</CardTitle>
              {data ? <Badge>{data.sources.length}</Badge> : null}
            </CardHeader>
            {isLoading ? (
              <CardContent>
                <Skeleton className="h-24 w-full" />
              </CardContent>
            ) : data && data.sources.length > 0 ? (
              <ul className="divide-y divide-border">
                {data.sources.map((source) => (
                  <li key={source.id} className="px-5 py-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="group min-w-0"
                      >
                        <span className="block truncate text-sm font-medium text-foreground group-hover:text-accent">
                          {source.title ?? source.url}
                        </span>
                        <span className="block truncate text-xs text-subtle">
                          {truncate(source.url, 90)}
                        </span>
                      </a>
                      <Badge tone={source.source_type === "search_result" ? "neutral" : "accent"}>
                        {humanize(source.source_type)}
                      </Badge>
                    </div>
                    {source.snippet ? (
                      <p className="mt-1.5 text-xs text-muted">{truncate(source.snippet, 220)}</p>
                    ) : null}
                    <p className="mt-1.5 flex flex-wrap gap-x-3 text-xs text-subtle">
                      {source.source_engine ? <span>via {source.source_engine}</span> : null}
                      {source.discovery_run_id ? (
                        <Link
                          href={`/runs/${source.discovery_run_id}`}
                          className="hover:text-accent"
                        >
                          Run #{source.discovery_run_id}
                        </Link>
                      ) : null}
                      <span>{formatDateTime(source.discovered_at)}</span>
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={Link2} title="No sources recorded" />
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-subtle">{label}</p>
      <div className="mt-0.5 text-sm text-foreground">{value}</div>
    </div>
  );
}
