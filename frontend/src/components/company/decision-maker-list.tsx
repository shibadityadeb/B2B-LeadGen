"use client";

import { ExternalLink, Mail, User } from "lucide-react";

import { ConfidenceBadge, VerificationBadge } from "@/components/domain/research-badges";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { humanize, truncate } from "@/lib/format";
import type { DecisionMaker } from "@/lib/types";

export function DecisionMakerList({ people }: { people: DecisionMaker[] }) {
  if (people.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={User}
          title="No names published"
          description="We only record people the company names on its own public pages. We never guess a name, and never make up an email address."
        />
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-subtle">
        Only what the company publishes itself. Where a job title is listed without a name,
        we leave the name blank rather than guessing.
      </p>
      {people.map((person) => (
        <Card key={person.id} className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">
                {person.name ?? <span className="italic text-muted">Name not published</span>}
              </p>
              <p className="mt-0.5 text-sm text-muted">{person.role}</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {person.role_category ? (
                <Badge tone="neutral">{humanize(person.role_category)}</Badge>
              ) : null}
              <VerificationBadge status={person.verification_status} />
            </div>
          </div>

          {person.excerpt ? (
            <p className="mt-2.5 rounded-lg bg-surface-muted/60 px-3 py-2 text-xs italic text-muted">
              “{person.excerpt}”
            </p>
          ) : null}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            {person.email ? (
              <a
                href={`mailto:${person.email}`}
                className="inline-flex items-center gap-1.5 text-xs text-accent hover:underline"
                title="This address is printed on the page. We never build one from a person's name."
              >
                <Mail className="size-3.5" />
                {person.email}
              </a>
            ) : (
              <span className="text-xs text-subtle">No email address published</span>
            )}
            <ConfidenceBadge level={person.confidence_level} />
          </div>

          {person.source_url ? (
            <a
              href={person.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-2 inline-flex max-w-full items-center gap-1.5 text-xs text-muted hover:text-accent"
            >
              <span className="truncate">{truncate(person.source_url, 70)}</span>
              <ExternalLink className="size-3 shrink-0" />
            </a>
          ) : null}
        </Card>
      ))}
    </div>
  );
}
