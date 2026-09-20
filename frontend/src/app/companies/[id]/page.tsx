"use client";

import {
  AlertTriangle,
  ExternalLink,
  FileText,
  Globe,
  History,
  Layers,
  Link2,
  Microscope,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { DecisionMakerList } from "@/components/company/decision-maker-list";
import { ResearchProgress } from "@/components/company/research-progress";
import { SignalList } from "@/components/company/signal-list";
import { EvidenceList } from "@/components/domain/evidence-list";
import { OpportunityCard } from "@/components/domain/opportunity-card";
import { PageHeader } from "@/components/domain/page-header";
import { ResearchStatusBadge } from "@/components/domain/research-badges";
import { CompanyStatusBadge, PageTypeBadge } from "@/components/domain/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Drawer } from "@/components/ui/drawer";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDateTime, formatNumber, humanize, truncate } from "@/lib/format";
import type { Evidence, Opportunity, Signal } from "@/lib/types";

type TabValue =
  | "overview"
  | "research"
  | "signals"
  | "opportunities"
  | "people"
  | "sources"
  | "history";

const TAB_VALUES: TabValue[] = [
  "overview",
  "research",
  "signals",
  "opportunities",
  "people",
  "sources",
  "history",
];

export default function CompanyDetailPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <CompanyDetailContent />
    </React.Suspense>
  );
}

function CompanyDetailContent() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const key = Number.isFinite(id) ? id : null;

  // The active tab lives in the URL so a refresh, a deep link and the back
  // button all land where the user expects.
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams.get("tab") as TabValue | null;
  const tab: TabValue = requested && TAB_VALUES.includes(requested) ? requested : "overview";

  const setTab = React.useCallback(
    (value: TabValue) => {
      const next = new URLSearchParams(searchParams.toString());
      if (value === "overview") next.delete("tab");
      else next.set("tab", value);
      const query = next.toString();
      router.replace(query ? `?${query}` : "?", { scroll: false });
    },
    [router, searchParams],
  );

  const [starting, setStarting] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [drawer, setDrawer] = React.useState<{
    title: string;
    description?: string;
    ids: number[];
  } | null>(null);
  const [pendingOpportunity, setPendingOpportunity] = React.useState<number | null>(null);
  const [outreachBusy, setOutreachBusy] = React.useState<number | null>(null);

  const company = useSWR(key ? ["company", key] : null, () => api.getCompany(id));
  const research = useSWR(key ? ["research", key] : null, () => api.companyResearch(id));
  const signals = useSWR(key ? ["signals", key] : null, () => api.companySignals(id));
  const opportunities = useSWR(key ? ["opps", key] : null, () => api.companyOpportunities(id));
  const people = useSWR(key ? ["people", key] : null, () => api.companyDecisionMakers(id));
  const evidence = useSWR(key ? ["evidence", key] : null, () => api.companyEvidence(id));
  const sources = useSWR(key ? ["rsources", key] : null, () => api.companyResearchSources(id));
  const contradictions = useSWR(key ? ["contra", key] : null, () => api.companyContradictions(id));

  const run = research.data?.latest_run ?? null;
  const researching =
    run?.status === "queued" || run?.status === "researching" || run?.status === "analyzing";

  // Poll only while a run is genuinely in flight, then refresh everything once.
  React.useEffect(() => {
    if (!researching) return;
    const timer = setInterval(() => research.mutate(), 2500);
    return () => clearInterval(timer);
  }, [researching, research]);

  const previousResearching = React.useRef(researching);
  React.useEffect(() => {
    if (previousResearching.current && !researching) {
      void Promise.all([
        company.mutate(),
        signals.mutate(),
        opportunities.mutate(),
        people.mutate(),
        evidence.mutate(),
        sources.mutate(),
        contradictions.mutate(),
      ]);
    }
    previousResearching.current = researching;
  }, [researching, company, signals, opportunities, people, evidence, sources, contradictions]);

  async function runResearch() {
    setStarting(true);
    setActionError(null);
    try {
      await api.startResearch(id);
      await research.mutate();
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : "Could not start research.",
      );
    } finally {
      setStarting(false);
    }
  }

  async function createOutreach(opportunity: Opportunity) {
    setOutreachBusy(opportunity.id);
    setActionError(null);
    try {
      // The backend reuses an existing outreach for the same opportunity and
      // recipient, so this is safe to click twice.
      const created = await api.createOutreach(opportunity.id);
      router.push(`/outreach/${created.id}`);
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : "Could not prepare the outreach.",
      );
      setOutreachBusy(null);
    }
  }

  async function setOpportunityStatus(opportunity: Opportunity, status: "dismissed" | "candidate") {
    setPendingOpportunity(opportunity.id);
    setActionError(null);
    try {
      await api.updateOpportunityStatus(opportunity.id, status);
      await opportunities.mutate();
    } catch (error) {
      setActionError(
        error instanceof ApiError ? error.message : "Could not update the opportunity.",
      );
    } finally {
      setPendingOpportunity(null);
    }
  }

  const evidenceById = React.useMemo(() => {
    const map = new Map<number, Evidence>();
    for (const item of evidence.data ?? []) map.set(item.id, item);
    return map;
  }, [evidence.data]);

  const drawerEvidence = React.useMemo(
    () => (drawer?.ids ?? []).map((itemId) => evidenceById.get(itemId)).filter(Boolean) as Evidence[],
    [drawer, evidenceById],
  );

  if (company.error) {
    return (
      <Card>
        <ErrorState
          title="Company not found"
          message={company.error.message}
          onRetry={() => company.mutate()}
        />
      </Card>
    );
  }

  const counts = research.data?.counts ?? {};
  const tabs = [
    { value: "overview", label: "Overview" },
    { value: "research", label: "Research", count: counts.evidence ?? 0 },
    { value: "signals", label: "Signals", count: counts.signals ?? 0 },
    { value: "opportunities", label: "Opportunities", count: counts.opportunities ?? 0 },
    { value: "people", label: "Decision makers", count: counts.decision_makers ?? 0 },
    { value: "sources", label: "Sources", count: counts.sources ?? 0 },
    { value: "history", label: "History", count: counts.runs ?? 0 },
  ];

  return (
    <>
      <PageHeader
        backHref="/companies"
        backLabel="Companies"
        title={company.data?.name ?? <Skeleton className="h-8 w-64" />}
        description={
          company.data ? (
            <span className="flex flex-wrap items-center gap-2">
              <a
                href={company.data.website_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1.5 font-mono text-sm text-accent hover:underline"
              >
                {company.data.canonical_domain}
                <ExternalLink className="size-3.5" />
              </a>
              {company.data.industry ? (
                <>
                  <span className="text-subtle">·</span>
                  <span>{company.data.industry}</span>
                </>
              ) : null}
              {company.data.location ? (
                <>
                  <span className="text-subtle">·</span>
                  <span>{company.data.location}</span>
                </>
              ) : null}
            </span>
          ) : undefined
        }
        actions={
          <>
            {research.data ? (
              <ResearchStatusBadge status={research.data.research_status} />
            ) : null}
            <Button onClick={runResearch} loading={starting || researching} disabled={!company.data}>
              <Microscope />
              {researching
                ? "Researching…"
                : research.data?.latest_run
                  ? "Refresh research"
                  : "Research company"}
            </Button>
          </>
        }
      />

      {actionError ? <InlineError className="mb-4" message={actionError} /> : null}

      {run ? (
        <div className="mb-5">
          <ResearchProgress run={run} onRetry={runResearch} retrying={starting} />
        </div>
      ) : null}

      <Tabs
        className="mb-5"
        items={tabs}
        value={tab}
        onChange={(value) => setTab(value as TabValue)}
      />

      {/* ------------------------------------------------ overview --- */}
      {tab === "overview" ? (
        <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Company</CardTitle>
              {company.data ? <CompanyStatusBadge status={company.data.status} /> : null}
            </CardHeader>
            <CardContent className="space-y-4">
              {!company.data ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <>
                  <Detail
                    label="Website"
                    value={
                      <a
                        href={company.data.website_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="break-all text-accent hover:underline"
                      >
                        {company.data.website_url}
                      </a>
                    }
                  />
                  <Detail label="Industry" value={company.data.industry ?? "Unknown"} />
                  <Detail label="Location" value={company.data.location ?? "Unknown"} />
                  <Detail label="Country" value={company.data.country ?? "Unknown"} />
                  <Detail
                    label="Company size"
                    value={company.data.company_size ? humanize(company.data.company_size) : "Unknown"}
                  />
                  <Detail label="Discovered" value={formatDateTime(company.data.created_at)} />
                  <Detail
                    label="Last researched"
                    value={
                      company.data.last_researched_at
                        ? formatDateTime(company.data.last_researched_at)
                        : "Never"
                    }
                  />
                  {company.data.first_discovery_run_id ? (
                    <Detail
                      label="First found by"
                      value={
                        <Link
                          href={`/runs/${company.data.first_discovery_run_id}`}
                          className="text-accent hover:underline"
                        >
                          Discovery run #{company.data.first_discovery_run_id}
                        </Link>
                      }
                    />
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>

          <div className="space-y-5">
            <Card>
              <CardHeader>
                <CardTitle>Website information</CardTitle>
                <span className="text-xs text-subtle">Extracted, not generated</span>
              </CardHeader>
              <CardContent>
                {!company.data ? (
                  <Skeleton className="h-20 w-full" />
                ) : company.data.summary.facts.length > 0 ? (
                  <>
                    <ul className="space-y-1.5">
                      {company.data.summary.facts.map((fact) => (
                        <li key={fact} className="flex gap-2 text-sm text-foreground">
                          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-subtle" />
                          {fact}
                        </li>
                      ))}
                    </ul>
                    {company.data.description ? (
                      <p className="mt-4 border-t border-border pt-4 text-sm text-muted">
                        <span className="font-medium text-foreground">From the homepage:</span>{" "}
                        “{company.data.description}”
                      </p>
                    ) : null}
                  </>
                ) : (
                  <EmptyState
                    icon={Globe}
                    title="No website information yet"
                    description="Run research to crawl the website and public sources."
                  />
                )}
              </CardContent>
            </Card>

            {(contradictions.data?.length ?? 0) > 0 ? (
              <Card className="border-warning/40 bg-warning-soft/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="size-4 text-warning" />
                    Conflicting public information
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {contradictions.data?.map((conflict) => (
                    <div key={conflict.id}>
                      <p className="text-sm text-foreground">{conflict.explanation}</p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mt-1"
                        onClick={() =>
                          setDrawer({
                            title: `Conflicting claims: ${humanize(conflict.subject)}`,
                            description: "Both claims are kept on record.",
                            ids: [conflict.evidence_a_id, conflict.evidence_b_id],
                          })
                        }
                      >
                        Compare evidence
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle>Pages crawled</CardTitle>
                {company.data ? <Badge>{company.data.pages.length}</Badge> : null}
              </CardHeader>
              {company.data && company.data.pages.length > 0 ? (
                <TableWrap>
                  <Table className="min-w-[32rem]">
                    <thead>
                      <tr>
                        <Th>Page</Th>
                        <Th>Type</Th>
                        <Th className="text-right">Content</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {company.data.pages.map((page) => (
                        <Tr key={page.id}>
                          <Td>
                            <a
                              href={page.url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="block max-w-sm truncate text-sm text-foreground hover:text-accent"
                            >
                              {page.title ?? page.url}
                            </a>
                          </Td>
                          <Td>
                            <PageTypeBadge type={page.page_type} />
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
                <EmptyState icon={Globe} title="No pages crawled yet" />
              )}
            </Card>
          </div>
        </div>
      ) : null}

      {/* ------------------------------------------------ research --- */}
      {tab === "research" ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <Card>
            <CardHeader>
              <CardTitle>Evidence</CardTitle>
              <span className="text-xs text-subtle">
                Every excerpt is copied verbatim from its source
              </span>
            </CardHeader>
            <CardContent>
              {evidence.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <EvidenceList
                  items={evidence.data ?? []}
                  emptyTitle="No evidence collected yet"
                  emptyDescription="Run research to collect evidence from the company website and public sources."
                />
              )}
            </CardContent>
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Research brief</CardTitle>
            </CardHeader>
            <CardContent>
              {research.data?.brief ? (
                <>
                  <p className="mb-3 text-xs text-subtle">
                    Generated {formatDateTime(research.data.brief.created_at)} ·{" "}
                    {research.data.brief.generated_by}
                  </p>
                  <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-3 text-xs leading-relaxed text-foreground">
                    {research.data.brief.markdown}
                  </pre>
                </>
              ) : (
                <EmptyState
                  icon={FileText}
                  title="No brief yet"
                  description="A brief is written at the end of each research run."
                />
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* ------------------------------------------------- signals --- */}
      {tab === "signals" ? (
        signals.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <SignalList
            signals={signals.data ?? []}
            onViewEvidence={(signal: Signal) =>
              setDrawer({
                title: signal.title,
                description: `${signal.evidence_count} evidence item(s) behind this signal`,
                ids: signal.evidence_ids,
              })
            }
          />
        )
      ) : null}

      {/* -------------------------------------------- opportunities --- */}
      {tab === "opportunities" ? (
        opportunities.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (opportunities.data?.length ?? 0) === 0 ? (
          <Card>
            <EmptyState
              icon={Layers}
              title="No potential opportunities yet"
              description="Opportunities are hypotheses derived from observed signals. Run research first."
            />
          </Card>
        ) : (
          <div className="space-y-4">
            <p className="text-xs text-subtle">
              These are hypotheses derived from public evidence — not established needs. Open
              the evidence behind each one before acting on it.
            </p>
            <div className="grid gap-4 xl:grid-cols-2">
              {opportunities.data?.map((opportunity) => (
                <OpportunityCard
                  key={opportunity.id}
                  opportunity={opportunity}
                  busy={pendingOpportunity === opportunity.id}
                  onViewEvidence={(item) =>
                    setDrawer({
                      title: item.title,
                      description: `Evidence behind this hypothesis · ${item.capability_name}`,
                      ids: item.evidence_ids,
                    })
                  }
                  onDismiss={(item) => setOpportunityStatus(item, "dismissed")}
                  onRestore={(item) => setOpportunityStatus(item, "candidate")}
                  onCreateOutreach={createOutreach}
                  outreachBusy={outreachBusy === opportunity.id}
                />
              ))}
            </div>
          </div>
        )
      ) : null}

      {/* -------------------------------------------------- people --- */}
      {tab === "people" ? (
        people.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <DecisionMakerList people={people.data ?? []} />
        )
      ) : null}

      {/* ------------------------------------------------- sources --- */}
      {tab === "sources" ? (
        <Card>
          <CardHeader>
            <CardTitle>Research sources</CardTitle>
            {sources.data ? <Badge>{sources.data.length}</Badge> : null}
          </CardHeader>
          {sources.isLoading ? (
            <CardContent>
              <Skeleton className="h-32 w-full" />
            </CardContent>
          ) : (sources.data?.length ?? 0) === 0 ? (
            <EmptyState
              icon={Link2}
              title="No sources retrieved yet"
              description="Sources are collected during a research run."
            />
          ) : (
            <TableWrap>
              <Table className="min-w-[44rem]">
                <thead>
                  <tr>
                    <Th>Source</Th>
                    <Th>Type</Th>
                    <Th>Reliability</Th>
                    <Th>Published</Th>
                    <Th className="text-right">Content</Th>
                  </tr>
                </thead>
                <tbody>
                  {sources.data?.map((source) => (
                    <Tr key={source.id}>
                      <Td>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="group block min-w-0 max-w-md"
                        >
                          <span className="block truncate text-sm text-foreground group-hover:text-accent">
                            {source.title ?? source.url}
                          </span>
                          <span className="block truncate text-xs text-subtle">
                            {truncate(source.url, 72)}
                          </span>
                        </a>
                      </Td>
                      <Td>
                        <Badge tone="neutral">{humanize(source.source_type)}</Badge>
                      </Td>
                      <Td>
                        <Badge
                          tone={source.source_reliability === "first_party" ? "accent" : "neutral"}
                          title="How directly this source speaks for the company."
                        >
                          {humanize(source.source_reliability)}
                        </Badge>
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {source.published_at ? formatDate(source.published_at) : "—"}
                      </Td>
                      <Td className="text-right tabular-nums text-muted">
                        {source.content_length > 0
                          ? `${formatNumber(source.content_length)}`
                          : source.retrieval_status === "skipped"
                            ? "skipped"
                            : "—"}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Card>
      ) : null}

      {/* ------------------------------------------------- history --- */}
      {tab === "history" ? (
        <Card>
          <CardHeader>
            <CardTitle>Research history</CardTitle>
            <span className="text-xs text-subtle">Earlier runs are never overwritten</span>
          </CardHeader>
          {(research.data?.runs.length ?? 0) === 0 ? (
            <EmptyState
              icon={History}
              title="No research runs yet"
              description="Each run is recorded here so you can see what changed between them."
            />
          ) : (
            <TableWrap>
              <Table className="min-w-[46rem]">
                <thead>
                  <tr>
                    <Th>Run</Th>
                    <Th>Started</Th>
                    <Th>Status</Th>
                    <Th className="text-right">Sources</Th>
                    <Th className="text-right">Evidence</Th>
                    <Th className="text-right">New</Th>
                    <Th className="text-right">Signals</Th>
                    <Th className="text-right">Opportunities</Th>
                  </tr>
                </thead>
                <tbody>
                  {research.data?.runs.map((item) => (
                    <Tr key={item.id}>
                      <Td>
                        <Link
                          href={`/research/${item.id}`}
                          className="font-medium text-foreground hover:text-accent"
                        >
                          #{item.id}
                        </Link>
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {formatDateTime(item.started_at ?? item.created_at)}
                      </Td>
                      <Td>
                        <ResearchStatusBadge status={item.status} />
                      </Td>
                      <Td className="text-right tabular-nums text-muted">
                        {item.sources_retrieved}
                      </Td>
                      <Td className="text-right tabular-nums text-muted">{item.evidence_count}</Td>
                      <Td className="text-right tabular-nums">
                        {item.new_evidence_count > 0 ? (
                          <Badge tone="accent">+{item.new_evidence_count}</Badge>
                        ) : (
                          <span className="text-muted">0</span>
                        )}
                      </Td>
                      <Td className="text-right tabular-nums text-muted">{item.signals_count}</Td>
                      <Td className="text-right tabular-nums text-muted">
                        {item.opportunities_count}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </Card>
      ) : null}

      <Drawer
        open={drawer !== null}
        title={drawer?.title ?? ""}
        description={drawer?.description}
        onClose={() => setDrawer(null)}
      >
        <EvidenceList
          items={drawerEvidence}
          emptyTitle="Evidence not loaded"
          emptyDescription="Open the Research tab to load the evidence for this company."
        />
      </Drawer>
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
