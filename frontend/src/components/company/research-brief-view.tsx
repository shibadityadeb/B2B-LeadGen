"use client";

import { Check, Copy, ExternalLink, FileText } from "lucide-react";
import * as React from "react";

import { FreshnessBadge } from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { formatDate, formatNumber, humanize, truncate } from "@/lib/format";
import { plain } from "@/lib/plain";

/**
 * Renders the research brief from the structured profile rather than from the
 * Markdown string. The Markdown is produced for export; showing it raw makes
 * headings, bullets and emphasis read as literal `#` and `**` characters.
 *
 * Rendering from the profile also turns every source into a real link.
 */

interface BriefEvidence {
  id: number;
  claim: string;
  excerpt: string | null;
  evidence_type: string;
  epistemic_status: string;
  freshness: string;
  freshness_basis?: string;
  published_at: string | null;
  source: { id: number; url: string; title: string | null } | null;
}

interface BriefProfile {
  company?: {
    name?: string;
    industry?: string | null;
    location?: string | null;
    website?: string;
    description?: string | null;
    identity_facts?: Record<string, { value: unknown; source_url?: string | null }>;
  };
  recent_activity?: BriefEvidence[];
  all_signals?: {
    id: number;
    type: string;
    title: string;
    freshness: string;
    confidence_level: string;
    evidence_count: number;
  }[];
  opportunities?: {
    id: number;
    title: string;
    capability: string | null;
    why_relevant: string;
    confidence_level: string;
    freshness: string;
    status: string;
    evidence_count: number;
  }[];
  decision_makers?: {
    id: number;
    name: string | null;
    role: string;
    email: string | null;
    verification_status: string;
    source_url: string | null;
  }[];
  uncertainties?: string[];
  sources?: { id: number; url: string; title: string | null; type: string; reliability: string }[];
}

export function ResearchBriefView({
  profile,
  markdown,
  generatedAt,
  generatedBy,
}: {
  profile: BriefProfile | null;
  markdown: string | null;
  generatedAt?: string;
  generatedBy?: string;
}) {
  const [copied, setCopied] = React.useState(false);
  const [showRaw, setShowRaw] = React.useState(false);

  async function copy() {
    if (!markdown) return;
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be blocked; the raw view is the fallback.
      setShowRaw(true);
    }
  }

  if (!profile && !markdown) {
    return (
      <EmptyState
        icon={FileText}
        title="No summary yet"
        description="A summary is written once this company has been researched."
      />
    );
  }

  const company = profile?.company;
  const facts = Object.entries(company?.identity_facts ?? {});

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-subtle">
          {generatedAt ? `Put together ${formatDate(generatedAt)}` : null}
          {generatedBy
            ? generatedBy.includes("llm")
              ? " · AI helped read the pages"
              : " · built from the pages themselves"
            : null}
        </p>
        <div className="flex gap-2">
          {markdown ? (
            <Button variant="ghost" size="sm" onClick={copy}>
              {copied ? <Check /> : <Copy />}
              {copied ? "Copied" : "Copy text"}
            </Button>
          ) : null}
          {markdown ? (
            <Button variant="ghost" size="sm" onClick={() => setShowRaw((value) => !value)}>
              {showRaw ? "Normal view" : "Plain text"}
            </Button>
          ) : null}
        </div>
      </div>

      {showRaw || !profile ? (
        <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap rounded-lg bg-surface-muted p-4 font-mono text-xs leading-relaxed text-foreground">
          {markdown}
        </pre>
      ) : (
        <div className="space-y-7">
          {/* --- header --- */}
          <header>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">
              {company?.name}
            </h2>
            <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
              <Meta label="Industry" value={company?.industry ?? "Unknown"} />
              <Meta label="Location" value={company?.location ?? "Unknown"} />
            </dl>
            {company?.website ? (
              <a
                href={company.website}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-1 inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
              >
                {company.website}
                <ExternalLink className="size-3.5" />
              </a>
            ) : null}
          </header>

          {/* --- about --- */}
          <Section title="About the company">
            {company?.description ? (
              <blockquote className="border-l-2 border-accent-border bg-surface-muted/50 px-3 py-2 text-sm italic text-muted">
                {company.description}
              </blockquote>
            ) : (
              <p className="text-sm italic text-muted">
They do not describe themselves on the pages we read.
              </p>
            )}
            {facts.length > 0 ? (
              <ul className="mt-3 space-y-1.5">
                {facts.map(([attribute, detail]) => (
                  <li key={attribute} className="text-sm text-foreground">
                    <span className="text-muted">{humanize(attribute)}:</span>{" "}
                    {String(detail.value)}
                    {detail.source_url ? (
                      <SourceLink url={detail.source_url} />
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </Section>

          {/* --- recent activity --- */}
          <Section title="What they've been doing" count={profile.recent_activity?.length}>
            {profile.recent_activity?.length ? (
              <ul className="space-y-4">
                {profile.recent_activity.map((item) => (
                  <li key={item.id}>
                    <p className="text-sm font-medium text-foreground">{item.claim}</p>
                    {item.excerpt ? (
                      <blockquote className="mt-1.5 border-l-2 border-border bg-surface-muted/50 px-3 py-2 text-sm italic text-muted">
                        “{item.excerpt}”
                      </blockquote>
                    ) : null}
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone="neutral">{plain.findingKind(item.evidence_type)}</Badge>
                      <FreshnessBadge
                        freshness={item.freshness as never}
                        basis={item.freshness_basis}
                      />
                      <Badge tone="neutral">{plain.certainty(item.epistemic_status).label}</Badge>
                      {item.published_at ? (
                        <span className="text-xs text-subtle">
                          {formatDate(item.published_at)}
                        </span>
                      ) : null}
                    </div>
                    {item.source?.url ? <SourceLink url={item.source.url} /> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <Empty text="No business activity was observed in the retrieved sources." />
            )}
          </Section>

          {/* --- signals --- */}
          <Section title="Patterns we noticed" count={profile.all_signals?.length}>
            {profile.all_signals?.length ? (
              <ul className="grid gap-2 sm:grid-cols-2">
                {profile.all_signals.map((signal) => (
                  <li
                    key={signal.id}
                    className="rounded-lg border border-border bg-surface px-3 py-2"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {plain.activity(signal.type)}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <FreshnessBadge freshness={signal.freshness as never} />
                      <Badge tone="neutral">{plain.strength(signal.confidence_level).label}</Badge>
                      <span className="text-xs text-subtle">
                        {signal.evidence_count} {signal.evidence_count === 1 ? "finding" : "findings"}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty text="Nothing consistent enough to call a pattern yet." />
            )}
          </Section>

          {/* --- opportunities --- */}
          <Section title="Where UBM might fit" count={profile.opportunities?.length}>
            <p className="mb-3 text-xs text-subtle">
              Ideas based on what we found in public — not confirmed needs.
            </p>
            {profile.opportunities?.length ? (
              <ol className="space-y-4">
                {profile.opportunities.map((item, index) => (
                  <li key={item.id} className="rounded-lg border border-border bg-surface p-4">
                    <p className="text-sm font-semibold text-foreground">
                      {index + 1}. {item.title}
                    </p>
                    {item.capability ? (
                      <Badge tone="accent" className="mt-1.5">
                        {item.capability}
                      </Badge>
                    ) : null}
                    <p className="mt-2 text-sm leading-relaxed text-muted">
                      {item.why_relevant}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Badge tone="neutral">Based on {item.evidence_count} {item.evidence_count === 1 ? "finding" : "findings"}</Badge>
                      <FreshnessBadge freshness={item.freshness as never} />
                      <Badge tone="neutral">{plain.strength(item.confidence_level).label}</Badge>
                      <Badge tone="neutral">{plain.opportunityStanding(item.status).label}</Badge>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <Empty text="Nothing we found points to a clear fit yet." />
            )}
          </Section>

          {/* --- people --- */}
          <Section title="People named publicly" count={profile.decision_makers?.length}>
            {profile.decision_makers?.length ? (
              <ul className="space-y-2">
                {profile.decision_makers.map((person) => (
                  <li
                    key={person.id}
                    className="rounded-lg border border-border bg-surface px-3 py-2"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {person.name ?? (
                        <span className="italic text-muted">Name not published</span>
                      )}
                    </p>
                    <p className="text-sm text-muted">{person.role}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <Badge tone="neutral">{plain.personTrust(person.verification_status).label}</Badge>
                      {person.email ? (
                        <a
                          href={`mailto:${person.email}`}
                          className="text-xs text-accent hover:underline"
                        >
                          {person.email}
                        </a>
                      ) : (
                        <span className="text-xs text-subtle">No email published</span>
                      )}
                    </div>
                    {person.source_url ? <SourceLink url={person.source_url} /> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <Empty text="No names or job titles are published on the pages we read." />
            )}
          </Section>

          {/* --- uncertainties --- */}
          <Section title="Where we're unsure" count={profile.uncertainties?.length}>
            {profile.uncertainties?.length ? (
              <ul className="space-y-1.5">
                {profile.uncertainties.map((note) => (
                  <li key={note} className="flex gap-2 text-sm text-muted">
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-warning" />
                    {note}
                  </li>
                ))}
              </ul>
            ) : (
              <Empty text="Nothing to flag." />
            )}
          </Section>

          {/* --- sources --- */}
          <Section title="Where this came from" count={profile.sources?.length}>
            {profile.sources?.length ? (
              <ul className="space-y-1.5">
                {profile.sources.map((source) => (
                  <li key={source.id} className="min-w-0">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="block truncate text-sm text-accent hover:underline"
                    >
                      {source.title ?? source.url}
                    </a>
                    <p className="truncate text-xs text-subtle">
                      {plain.sourceTrust(source.reliability).label} ·{" "}
                      {truncate(source.url, 64)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty text="No pages were read." />
            )}
          </Section>
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="mb-3 flex items-center gap-2 border-b border-border pb-2 text-sm font-semibold uppercase tracking-wide text-subtle">
        {title}
        {count !== undefined && count > 0 ? (
          <span className="rounded-full bg-surface-muted px-1.5 py-0.5 text-xs tabular-nums normal-case text-muted">
            {formatNumber(count)}
          </span>
        ) : null}
      </h3>
      {children}
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-1.5">
      <dt className="text-muted">{label}:</dt>
      <dd className="text-foreground">{value}</dd>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm italic text-muted">{text}</p>;
}

function SourceLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      className="mt-1 inline-flex max-w-full items-center gap-1.5 text-xs text-accent hover:underline"
    >
      <span className="truncate">{truncate(url, 72)}</span>
      <ExternalLink className="size-3 shrink-0" />
    </a>
  );
}
