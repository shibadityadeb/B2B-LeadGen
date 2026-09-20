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
import { ResearchBriefView } from "@/components/company/research-brief-view";
import { ResearchProgress } from "@/components/company/research-progress";
import { SignalList } from "@/components/company/signal-list";
import { EvidenceList } from "@/components/domain/evidence-list";
import { OpportunityCard } from "@/components/domain/opportunity-card";
import { PageHeader } from "@/components/domain/page-header";
import { ResearchStatusBadge } from "@/components/domain/research-badges";
import { CompanyStatusBadge } from "@/components/domain/status";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Drawer } from "@/components/ui/drawer";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/states";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import { plain } from "@/lib/plain";
import { formatDate, formatDateTime, humanize, truncate } from "@/lib/format";
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

  // Whether this company has ever been checked. An empty tab means something
  // different before and after: "we haven't looked" versus "we looked and
  // there was nothing" — and saying the wrong one is misleading.
  const hasBeenResearched = Boolean(research.data?.latest_run?.completed_at);

  const researchLabel = researching
    ? "Researching…"
    : research.data?.latest_run
      ? "Refresh research"
      : "Research company";

  // The same working button, reused wherever a tab is empty — nobody should
  // have to go looking for it.
  const researchButton = (
    <Button onClick={runResearch} loading={starting || researching} disabled={!company.data}>
      <Microscope /> {researchLabel}
    </Button>
  );

  // A company's own site can be read by the original page crawl or by a
  // research run. The operator should not have to know which one ran, so the
  // Overview draws on whichever actually produced something.
  const briefCompany = (
    research.data?.brief?.profile as { company?: Record<string, unknown> } | undefined
  )?.company;
  const identityFacts = Object.entries(
    (briefCompany?.identity_facts as
      | Record<string, { value: unknown; source_url?: string }>
      | undefined) ?? {},
  );
  // Verbatim sentences from the company's own pages describing what they do.
  const aboutLines =
    (briefCompany?.about as
      | { text: string; source_url: string; source_title?: string | null }[]
      | undefined) ?? [];
  const legacyFacts = company.data?.summary.facts ?? [];
  const websiteDescription =
    (briefCompany?.description as string | undefined) ?? company.data?.description ?? null;
  const hasWebsiteInfo =
    aboutLines.length > 0 ||
    identityFacts.length > 0 ||
    legacyFacts.length > 0 ||
    Boolean(websiteDescription);

  // Pages from the company's own domain, from either pass.
  const ownSitePages = (sources.data ?? []).filter(
    (source) => source.source_reliability === "first_party",
  );

  const counts = research.data?.counts ?? {};
  const tabs = [
    { value: "overview", label: "Overview" },
    { value: "research", label: "What we found", count: counts.evidence ?? 0 },
    { value: "signals", label: "What they're doing", count: counts.signals ?? 0 },
    { value: "opportunities", label: "Opportunities", count: counts.opportunities ?? 0 },
    { value: "people", label: "People", count: counts.decision_makers ?? 0 },
    { value: "sources", label: "Sources", count: counts.sources ?? 0 },
    { value: "history", label: "Past checks", count: counts.runs ?? 0 },
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
            {researchButton}
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
                <CardTitle>From their website</CardTitle>
                <span className="text-xs text-subtle">
                  Copied from their pages, not written by AI
                </span>
              </CardHeader>
              <CardContent>
                {!company.data ? (
                  <Skeleton className="h-20 w-full" />
                ) : hasWebsiteInfo ? (
                  <>
                    {aboutLines.length > 0 ? (
                      <ul className="space-y-3">
                        {aboutLines.map((line) => (
                          <li key={line.text}>
                            <blockquote className="border-l-2 border-accent-border bg-surface-muted/50 px-3 py-2 text-sm leading-relaxed text-foreground">
                              “{line.text}”
                            </blockquote>
                            <a
                              href={line.source_url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="mt-1 inline-flex max-w-full items-center gap-1 text-xs text-accent hover:underline"
                            >
                              <span className="truncate">{truncate(line.source_url, 62)}</span>
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <ul className={aboutLines.length > 0 ? "mt-4 space-y-1.5 border-t border-border pt-4" : "space-y-1.5"}>
                      {identityFacts.map(([attribute, detail]) => (
                        <li key={attribute} className="text-sm text-foreground">
                          <span className="text-muted">{humanize(attribute)}:</span>{" "}
                          {String(detail.value)}
                          {detail.source_url ? (
                            <a
                              href={detail.source_url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="ml-2 text-xs text-accent hover:underline"
                            >
                              source
                            </a>
                          ) : null}
                        </li>
                      ))}
                      {legacyFacts.map((fact) => (
                        <li key={fact} className="flex gap-2 text-sm text-foreground">
                          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-subtle" />
                          {fact}
                        </li>
                      ))}
                    </ul>
                    {aboutLines.length === 0 && websiteDescription ? (
                      <p className="mt-4 border-t border-border pt-4 text-sm text-muted">
                        <span className="font-medium text-foreground">
                          How they describe themselves:
                        </span>{" "}
                        “{websiteDescription}”
                      </p>
                    ) : null}
                  </>
                ) : (
                  <EmptyState
                    icon={Globe}
                    title={
                      hasBeenResearched
                        ? "Nothing usable on their website"
                        : "Their website has not been read yet"
                    }
                    description={
                      hasBeenResearched
                        ? "We read their site but could not pull anything meaningful from it. Checking again may help if they have since updated it."
                        : "We can read their website and any public pages that mention them."
                    }
                    action={researchButton}
                  />
                )}
              </CardContent>
            </Card>

            {(contradictions.data?.length ?? 0) > 0 ? (
              <Card className="border-warning/40 bg-warning-soft/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="size-4 text-warning" />
                    Sources disagree
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
                        See both
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle>Pages read on their site</CardTitle>
                {ownSitePages.length > 0 ? <Badge>{ownSitePages.length}</Badge> : null}
              </CardHeader>
              {ownSitePages.length > 0 ? (
                <TableWrap>
                  <Table className="min-w-[32rem]">
                    <thead>
                      <tr>
                        <Th>Page</Th>
                        <Th>Kind</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {ownSitePages.map((page) => (
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
                            <span className="block max-w-sm truncate text-xs text-subtle">
                              {truncate(page.url, 58)}
                            </span>
                          </Td>
                          <Td>
                            <Badge tone="neutral">
                              {humanize(page.source_type.replace("company_", ""))}
                            </Badge>
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </TableWrap>
              ) : (
                <EmptyState
                icon={Globe}
                title={
                  hasBeenResearched
                    ? "We could not read their own website"
                    : "Their website has not been read yet"
                }
                description={
                  hasBeenResearched
                    ? "Their site did not respond or blocked us. Other public pages about them are listed under Sources."
                    : undefined
                }
                action={hasBeenResearched ? undefined : researchButton}
              />
              )}
            </Card>
          </div>
        </div>
      ) : null}

      {/* ------------------------------------------------ research --- */}
      {tab === "research" ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_30rem]">
          <Card>
            <CardHeader>
              <CardTitle>What we found about this company</CardTitle>
              <span className="text-xs text-subtle">
                Every quote is copied word for word — open the source to check it
              </span>
            </CardHeader>
            <CardContent>
              {evidence.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <EvidenceList
                  items={evidence.data ?? []}
                  emptyTitle={
                    hasBeenResearched ? "We found nothing to report" : "Not looked yet"
                  }
                  emptyDescription={
                    hasBeenResearched
                      ? "We read their pages but found nothing specific enough to rely on. That is a real answer, not an error — some companies publish very little."
                      : "We can look through their website and any public pages that mention them."
                  }
                  emptyAction={researchButton}
                />
              )}
            </CardContent>
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {research.data?.brief ? (
                <div className="max-h-[40rem] overflow-y-auto pr-1">
                  <ResearchBriefView
                    profile={
                      (research.data.brief.profile as Record<string, unknown>) ?? null
                    }
                    markdown={research.data.brief.markdown}
                    generatedAt={research.data.brief.created_at}
                    generatedBy={research.data.brief.generated_by}
                  />
                </div>
              ) : (
                <EmptyState
                  icon={FileText}
                  title="No summary yet"
                  description="A summary is written once the company has been researched."
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
            emptyAction={researchButton}
            hasBeenResearched={hasBeenResearched}
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
              title={
                hasBeenResearched ? "No openings to suggest" : "Nothing to suggest yet"
              }
              description={
                hasBeenResearched
                  ? "Nothing this company is doing publicly points to a fit with UBM right now. Worth checking again in a few weeks."
                  : "Openings are worked out from what a company appears to be doing, so we need to look first."
              }
              action={researchButton}
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
          <DecisionMakerList
            people={people.data ?? []}
            emptyAction={researchButton}
            hasBeenResearched={hasBeenResearched}
          />
        )
      ) : null}

      {/* ------------------------------------------------- sources --- */}
      {tab === "sources" ? (
        <Card>
          <CardHeader>
            <CardTitle>Where this came from</CardTitle>
            {sources.data ? <Badge>{sources.data.length}</Badge> : null}
          </CardHeader>
          {sources.isLoading ? (
            <CardContent>
              <Skeleton className="h-32 w-full" />
            </CardContent>
          ) : (sources.data?.length ?? 0) === 0 ? (
            <EmptyState
              icon={Link2}
              title="No pages read yet"
              description="Every page we read is listed here, so you can check anything yourself."
              action={researchButton}
            />
          ) : (
            <TableWrap>
              <Table className="min-w-[44rem]">
                <thead>
                  <tr>
                    <Th>Page</Th>
                    <Th>Kind</Th>
                    <Th>Who published it</Th>
                    <Th>Date</Th>
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
                          title={plain.sourceTrust(source.source_reliability).help}
                        >
                          {plain.sourceTrust(source.source_reliability).label}
                        </Badge>
                      </Td>
                      <Td className="whitespace-nowrap text-muted">
                        {source.published_at ? formatDate(source.published_at) : "Not shown"}
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
            <CardTitle>Past checks</CardTitle>
            <span className="text-xs text-subtle">Nothing from an earlier check is ever deleted</span>
          </CardHeader>
          {(research.data?.runs.length ?? 0) === 0 ? (
            <EmptyState
              icon={History}
              title="Not checked yet"
              description="Each check is recorded here, so you can see what changed since last time."
              action={researchButton}
            />
          ) : (
            <TableWrap>
              <Table className="min-w-[46rem]">
                <thead>
                  <tr>
                    <Th>When</Th>
                    <Th>Result</Th>
                    <Th className="text-right">Things found</Th>
                    <Th className="text-right">New since last time</Th>
                    <Th className="text-right">Opportunities</Th>
                  </tr>
                </thead>
                <tbody>
                  {research.data?.runs.map((item) => (
                    <Tr key={item.id}>
                      <Td className="whitespace-nowrap">
                        <Link
                          href={`/research/${item.id}`}
                          className="font-medium text-foreground hover:text-accent"
                        >
                          {formatDateTime(item.started_at ?? item.created_at)}
                        </Link>
                      </Td>
                      <Td>
                        <ResearchStatusBadge status={item.status} />
                      </Td>
                      <Td className="text-right tabular-nums text-muted">{item.evidence_count}</Td>
                      <Td className="text-right tabular-nums">
                        {item.new_evidence_count > 0 ? (
                          <Badge tone="accent">+{item.new_evidence_count}</Badge>
                        ) : (
                          <span className="text-muted">none</span>
                        )}
                      </Td>
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
