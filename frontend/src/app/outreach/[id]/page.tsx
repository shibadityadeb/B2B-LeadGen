"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  History,
  Mail,
  Send,
  ThumbsDown,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { EmailComposer } from "@/components/outreach/email-composer";
import {
  OutcomeBadge,
  OutreachStatusBadge,
  ValidationBadge,
} from "@/components/outreach/outreach-badges";
import { ValidationPanel } from "@/components/outreach/validation-panel";
import { WhyThisEmail } from "@/components/outreach/why-this-email";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Drawer } from "@/components/ui/drawer";
import { Field, Select, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/states";
import { Tabs } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDateTime, humanize } from "@/lib/format";
import type {
  MessageLength,
  OutcomeReason,
  OutcomeStatus,
  OutreachTone,
  ValidationResult,
} from "@/lib/types";

const OUTCOMES: { value: OutcomeStatus; label: string }[] = [
  { value: "no_response", label: "No response" },
  { value: "replied", label: "Replied" },
  { value: "interested", label: "Interested" },
  { value: "not_interested", label: "Not interested" },
  { value: "meeting_scheduled", label: "Meeting scheduled" },
  { value: "opportunity_won", label: "Opportunity won" },
  { value: "opportunity_lost", label: "Opportunity lost" },
  { value: "do_not_contact", label: "Do not contact" },
];

const REASONS: { value: OutcomeReason; label: string }[] = [
  { value: "wrong_opportunity", label: "Wrong opportunity" },
  { value: "wrong_person", label: "Wrong person" },
  { value: "wrong_company", label: "Wrong company" },
  { value: "timing", label: "Timing" },
  { value: "already_has_provider", label: "Already has a provider" },
  { value: "no_budget", label: "No budget" },
  { value: "not_relevant", label: "Not relevant" },
  { value: "other", label: "Other" },
];

type TabValue = "review" | "versions" | "activity";

export default function OutreachDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const outreach = useSWR(Number.isFinite(id) ? ["outreach", id] : null, () =>
    api.getOutreach(id),
  );
  const gmail = useSWR("gmail-status", api.gmailStatus);
  const sender = useSWR("sender-profile", api.getSenderProfile);

  const [tab, setTab] = React.useState<TabValue>("review");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmReject, setConfirmReject] = React.useState(false);
  const [outcomeOpen, setOutcomeOpen] = React.useState(false);
  const [outcomeStatus, setOutcomeStatus] = React.useState<OutcomeStatus>("replied");
  const [outcomeReason, setOutcomeReason] = React.useState<OutcomeReason | "">("");
  const [outcomeNotes, setOutcomeNotes] = React.useState("");

  const data = outreach.data;
  const validation = (data?.validation ?? null) as ValidationResult | null;

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await outreach.mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  if (outreach.error) {
    return (
      <Card>
        <ErrorState
          title="Outreach not found"
          message={outreach.error.message}
          onRetry={() => outreach.mutate()}
        />
      </Card>
    );
  }

  const canApprove = data?.status === "review" || data?.status === "draft";
  const canGmail = data?.status === "approved" || data?.status === "gmail_draft_created";
  const canMarkSent = data?.status === "approved" || data?.status === "gmail_draft_created";
  const canFollowUp = data?.status === "sent" || data?.status === "follow_up_due";

  return (
    <>
      <PageHeader
        backHref="/outreach"
        backLabel="Outreach"
        title={
          data ? (
            <span className="flex flex-wrap items-center gap-2">
              {data.company_name}
              {data.follow_up_number > 0 ? (
                <Badge tone="neutral">Follow-up #{data.follow_up_number}</Badge>
              ) : null}
            </span>
          ) : (
            <Skeleton className="h-8 w-64" />
          )
        }
        description={
          data ? (
            <span className="flex flex-wrap items-center gap-2">
              <Link
                href={`/companies/${data.company_id}?tab=opportunities`}
                className="text-accent hover:underline"
              >
                {data.capability_name ?? data.opportunity_title}
              </Link>
              <span className="text-subtle">·</span>
              <span>{data.to_name ?? data.recipient_role ?? "No recipient"}</span>
              {data.campaign_name ? (
                <>
                  <span className="text-subtle">·</span>
                  <span>{data.campaign_name}</span>
                </>
              ) : null}
            </span>
          ) : undefined
        }
        actions={
          data ? (
            <>
              <OutreachStatusBadge status={data.status} />
              {validation ? (
                <ValidationBadge
                  valid={validation.valid}
                  errors={validation.errors?.length ?? 0}
                  warnings={validation.warnings?.length ?? 0}
                />
              ) : null}
            </>
          ) : undefined
        }
      />

      {error ? <InlineError className="mb-4" message={error} /> : null}

      {/* --- the action bar: approval gates everything --- */}
      {data ? (
        <Card className="mb-5">
          <CardContent className="flex flex-wrap items-center gap-2">
            {canApprove ? (
              <Button
                onClick={() => run("approve", () => api.approveOutreach(id))}
                loading={busy === "approve"}
                disabled={validation ? !validation.valid : false}
                title={
                  validation && !validation.valid
                    ? "Resolve the validation errors first"
                    : undefined
                }
              >
                <CheckCircle2 /> Approve
              </Button>
            ) : null}

            {canGmail ? (
              <Button
                variant={data.gmail_draft_id ? "secondary" : "primary"}
                onClick={() => run("gmail", () => api.createGmailDraft(id))}
                loading={busy === "gmail"}
                disabled={!data.to_email}
                title={!data.to_email ? "Add a recipient email address first" : undefined}
              >
                <Mail />
                {data.gmail_draft_id ? "Gmail draft created" : "Create Gmail draft"}
              </Button>
            ) : null}

            {data.gmail_draft_url ? (
              <a
                href={data.gmail_draft_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
              >
                Open in Gmail <ExternalLink className="size-3.5" />
              </a>
            ) : null}

            {canMarkSent ? (
              <Button
                variant="secondary"
                onClick={() => run("sent", () => api.markSent(id))}
                loading={busy === "sent"}
                title="Record that you sent this yourself from your mail client"
              >
                <Send /> Mark as sent
              </Button>
            ) : null}

            {canFollowUp ? (
              <Button
                variant="secondary"
                onClick={() => run("follow", () => api.createFollowUpDraft(id))}
                loading={busy === "follow"}
              >
                <Clock /> Create follow-up draft
              </Button>
            ) : null}

            {data.sent_at ? (
              <Button variant="secondary" onClick={() => setOutcomeOpen(true)}>
                Record outcome
              </Button>
            ) : null}

            {canApprove || canGmail ? (
              <Button
                variant="ghost"
                onClick={() => setConfirmReject(true)}
                loading={busy === "reject"}
              >
                <ThumbsDown /> Reject
              </Button>
            ) : null}

            <span className="ml-auto text-xs text-subtle">
              Nothing is sent automatically — you send from your own mailbox.
            </span>
          </CardContent>
        </Card>
      ) : null}

      {/* --- gmail connection notice --- */}
      {data && canGmail && gmail.data && !gmail.data.connected ? (
        <Card className="mb-5 border-warning/40 bg-warning-soft/40">
          <CardContent className="flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-sm text-foreground">
              <AlertTriangle className="size-4 text-warning" />
              {gmail.data.detail ?? "Gmail is not connected."}
            </p>
            <Link href="/settings" className="text-sm text-accent hover:underline">
              Connect Gmail in Settings
            </Link>
          </CardContent>
        </Card>
      ) : null}

      {/* --- status timeline --- */}
      {data ? (
        <Card className="mb-5">
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Stat label="Approved" value={data.approved_at ? formatDateTime(data.approved_at) : "—"} />
              <Stat
                label="Gmail draft"
                value={
                  data.gmail_draft_created_at ? formatDateTime(data.gmail_draft_created_at) : "—"
                }
              />
              <Stat label="Marked sent" value={data.sent_at ? formatDateTime(data.sent_at) : "—"} />
              <Stat
                label="Next follow-up"
                value={
                  data.next_follow_up_at ? (
                    <span className={data.follow_up_due ? "text-warning" : undefined}>
                      {formatDate(data.next_follow_up_at)}
                      {data.follow_up_due ? " (due)" : ""}
                    </span>
                  ) : (
                    "—"
                  )
                }
              />
            </dl>
            {data.outcome_status ? (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
                <span className="text-xs uppercase tracking-wide text-subtle">Outcome</span>
                <OutcomeBadge status={data.outcome_status} />
                {data.outcome_reason ? (
                  <Badge tone="neutral">{humanize(data.outcome_reason)}</Badge>
                ) : null}
                {data.outcome_notes ? (
                  <span className="text-sm text-muted">{data.outcome_notes}</span>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Tabs
        className="mb-5"
        items={[
          { value: "review", label: "Review" },
          { value: "versions", label: "Versions", count: data?.versions.length ?? 0 },
          { value: "activity", label: "Activity", count: data?.audit.length ?? 0 },
        ]}
        value={tab}
        onChange={(value) => setTab(value as TabValue)}
      />

      {tab === "review" ? (
        !data ? (
          <Skeleton className="h-96 w-full" />
        ) : (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_26rem]">
            <div className="space-y-5">
              <EmailComposer
                outreach={data}
                senderEmail={gmail.data?.account_email ?? sender.data?.email ?? null}
                saving={busy === "save"}
                regenerating={busy === "regen"}
                onSave={(payload) => run("save", () => api.updateOutreach(id, payload))}
                onRegenerate={(payload) =>
                  run("regen", () =>
                    api.regenerateOutreach(id, {
                      tone: payload.tone as OutreachTone,
                      message_length: payload.message_length as MessageLength,
                    }),
                  )
                }
                onReset={() => run("save", () => api.resetOutreach(id))}
              />
              <ValidationPanel validation={validation} />
            </div>
            <div className="space-y-5">
              <WhyThisEmail outreach={data} />
              {data.follow_ups.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Follow-ups</CardTitle>
                  </CardHeader>
                  <ul className="divide-y divide-border">
                    {data.follow_ups.map((item) => (
                      <li key={item.id}>
                        <Link
                          href={`/outreach/${item.id}`}
                          className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-surface-muted/50"
                        >
                          <span className="text-sm text-foreground">
                            Follow-up #{item.follow_up_number}
                          </span>
                          <OutreachStatusBadge status={item.status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                </Card>
              ) : null}
            </div>
          </div>
        )
      ) : null}

      {tab === "versions" ? (
        <Card>
          <CardHeader>
            <CardTitle>Version history</CardTitle>
            <span className="text-xs text-subtle">Regenerating never destroys a version</span>
          </CardHeader>
          {!data || data.versions.length === 0 ? (
            <EmptyState icon={History} title="No versions yet" />
          ) : (
            <ul className="divide-y divide-border">
              {[...data.versions].reverse().map((version) => (
                <li key={version.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
                        Version {version.version_number}
                        {version.is_active ? <Badge tone="accent">Active</Badge> : null}
                        <Badge tone="neutral">{humanize(version.generation_method)}</Badge>
                      </p>
                      <p className="mt-0.5 text-xs text-subtle">
                        {formatDateTime(version.created_at)}
                      </p>
                    </div>
                    {!version.is_active && data.status !== "sent" ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        loading={busy === `v-${version.id}`}
                        onClick={() =>
                          run(`v-${version.id}`, () => api.activateVersion(id, version.id))
                        }
                      >
                        Use this version
                      </Button>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm font-medium text-foreground">{version.subject}</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-muted">{version.body}</p>

                  {version.claims.filter((claim) => claim.requires_evidence).length > 0 ? (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-xs font-medium text-accent">
                        Evidence behind this version
                      </summary>
                      <ul className="mt-2 space-y-2">
                        {version.claims
                          .filter((claim) => claim.requires_evidence)
                          .map((claim) => (
                            <li
                              key={claim.id}
                              className="rounded-lg border border-border bg-surface-muted/40 p-3"
                            >
                              <p className="text-sm text-foreground">{claim.text}</p>
                              {claim.evidence.map((reference) => (
                                <div key={reference.evidence_id} className="mt-1.5">
                                  <p className="text-xs italic text-muted">
                                    “{reference.excerpt}”
                                  </p>
                                  {reference.source_url ? (
                                    <a
                                      href={reference.source_url}
                                      target="_blank"
                                      rel="noreferrer noopener"
                                      className="text-xs text-accent hover:underline"
                                    >
                                      {reference.source_url}
                                    </a>
                                  ) : null}
                                </div>
                              ))}
                            </li>
                          ))}
                      </ul>
                    </details>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      {tab === "activity" ? (
        <Card>
          <CardHeader>
            <CardTitle>Activity</CardTitle>
          </CardHeader>
          {!data || data.audit.length === 0 ? (
            <EmptyState title="No activity recorded" />
          ) : (
            <ul className="divide-y divide-border">
              {data.audit.map((event) => (
                <li key={event.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                  <Badge tone="neutral">{humanize(event.action)}</Badge>
                  <span className="text-sm text-muted">{event.actor ?? "local"}</span>
                  <span className="ml-auto text-xs text-subtle">
                    {formatDateTime(event.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirmReject}
        loading={busy === "reject"}
        title="Reject this outreach?"
        description="The message is kept, along with every version and its evidence. You can rework and resubmit it later."
        confirmLabel="Reject"
        onCancel={() => setConfirmReject(false)}
        onConfirm={async () => {
          await run("reject", () => api.rejectOutreach(id));
          setConfirmReject(false);
        }}
      />

      <Drawer
        open={outcomeOpen}
        title="Record the outcome"
        description="What actually happened after you sent this."
        onClose={() => setOutcomeOpen(false)}
      >
        <div className="space-y-4">
          <Field label="Outcome" htmlFor="outcome">
            <Select
              id="outcome"
              value={outcomeStatus}
              onChange={(event) => setOutcomeStatus(event.target.value as OutcomeStatus)}
            >
              {OUTCOMES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Reason"
            htmlFor="reason"
            hint="Optional. Stored as structured feedback for improving the opportunity engine later."
          >
            <Select
              id="reason"
              value={outcomeReason}
              onChange={(event) => setOutcomeReason(event.target.value as OutcomeReason)}
            >
              <option value="">No reason given</option>
              {REASONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Notes" htmlFor="notes">
            <Textarea
              id="notes"
              value={outcomeNotes}
              onChange={(event) => setOutcomeNotes(event.target.value)}
              placeholder="Anything worth remembering."
            />
          </Field>
          <Button
            loading={busy === "outcome"}
            onClick={async () => {
              await run("outcome", () =>
                api.updateOutcome(id, {
                  status: outcomeStatus,
                  reason: outcomeReason || null,
                  notes: outcomeNotes || null,
                }),
              );
              setOutcomeOpen(false);
            }}
          >
            Save outcome
          </Button>
        </div>
      </Drawer>
    </>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-subtle">{label}</dt>
      <dd className="mt-0.5 text-sm text-foreground">{value}</dd>
    </div>
  );
}
