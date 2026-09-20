"use client";

import { RotateCcw, Sparkles } from "lucide-react";
import * as React from "react";

import { EditedBadge } from "@/components/outreach/outreach-badges";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import type { MessageLength, Outreach, OutreachTone } from "@/lib/types";

const TONES: { value: OutreachTone; label: string }[] = [
  { value: "professional", label: "Professional" },
  { value: "conversational", label: "Conversational" },
  { value: "direct", label: "Direct" },
  { value: "warm", label: "Warm" },
];

const LENGTHS: { value: MessageLength; label: string }[] = [
  { value: "short", label: "Short (default)" },
  { value: "medium", label: "Medium" },
];

/**
 * Preview and editor in one. Reads like a mail composer so the reviewer sees
 * what the recipient will see, and every field is editable before approval.
 */
export function EmailComposer({
  outreach,
  senderEmail,
  onSave,
  onRegenerate,
  onReset,
  saving,
  regenerating,
}: {
  outreach: Outreach;
  senderEmail: string | null;
  onSave: (payload: {
    subject?: string;
    body?: string;
    to_email?: string;
    to_name?: string;
    cc?: string;
    bcc?: string;
  }) => Promise<void>;
  onRegenerate: (payload: { tone?: OutreachTone; message_length?: MessageLength }) => Promise<void>;
  onReset: () => Promise<void>;
  saving?: boolean;
  regenerating?: boolean;
}) {
  const [editing, setEditing] = React.useState(false);
  const [subject, setSubject] = React.useState(outreach.subject ?? "");
  const [body, setBody] = React.useState(outreach.body ?? "");
  const [toEmail, setToEmail] = React.useState(outreach.to_email ?? "");
  const [cc, setCc] = React.useState(outreach.cc ?? "");
  const [bcc, setBcc] = React.useState(outreach.bcc ?? "");
  const [tone, setTone] = React.useState<OutreachTone>(outreach.tone);
  const [length, setLength] = React.useState<MessageLength>(outreach.message_length);

  // Re-sync when a regeneration or version switch changes the content, but
  // never while the user is mid-edit — their text is not overwritten.
  React.useEffect(() => {
    if (editing) return;
    setSubject(outreach.subject ?? "");
    setBody(outreach.body ?? "");
    setToEmail(outreach.to_email ?? "");
    setCc(outreach.cc ?? "");
    setBcc(outreach.bcc ?? "");
  }, [outreach.subject, outreach.body, outreach.to_email, outreach.cc, outreach.bcc, editing]);

  const locked = outreach.status === "sent" || outreach.status === "completed";

  async function save() {
    await onSave({ subject, body, to_email: toEmail, cc, bcc });
    setEditing(false);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Email</CardTitle>
          {outreach.user_edited ? <EditedBadge /> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {!locked ? (
            editing ? (
              <>
                <Button size="sm" onClick={save} loading={saving}>
                  Save changes
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setEditing(false);
                    setSubject(outreach.subject ?? "");
                    setBody(outreach.body ?? "");
                  }}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )
          ) : null}
          {outreach.user_edited && !editing && !locked ? (
            <Button size="sm" variant="ghost" onClick={onReset} loading={saving}>
              <RotateCcw /> Reset to generated
            </Button>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* --- headers --- */}
        <div className="rounded-lg border border-border bg-surface-muted/40 p-3">
          <dl className="space-y-2 text-sm">
            <div className="flex gap-3">
              <dt className="w-12 shrink-0 text-xs uppercase tracking-wide text-subtle">From</dt>
              <dd className="min-w-0 break-all text-muted">
                {senderEmail ?? "Your connected mailbox"}
              </dd>
            </div>
            <div className="flex items-center gap-3">
              <dt className="w-12 shrink-0 text-xs uppercase tracking-wide text-subtle">To</dt>
              <dd className="min-w-0 flex-1">
                {editing ? (
                  <Input
                    value={toEmail}
                    onChange={(event) => setToEmail(event.target.value)}
                    placeholder="name@company.com"
                    aria-label="Recipient email"
                  />
                ) : outreach.to_email ? (
                  <span className="break-all text-foreground">
                    {outreach.to_name ? `${outreach.to_name} <${outreach.to_email}>` : outreach.to_email}
                  </span>
                ) : (
                  <span className="text-danger">
                    No email address — add one before creating a Gmail draft
                  </span>
                )}
              </dd>
            </div>
            {editing ? (
              <>
                <div className="flex items-center gap-3">
                  <dt className="w-12 shrink-0 text-xs uppercase tracking-wide text-subtle">Cc</dt>
                  <dd className="min-w-0 flex-1">
                    <Input value={cc} onChange={(event) => setCc(event.target.value)} aria-label="Cc" />
                  </dd>
                </div>
                <div className="flex items-center gap-3">
                  <dt className="w-12 shrink-0 text-xs uppercase tracking-wide text-subtle">Bcc</dt>
                  <dd className="min-w-0 flex-1">
                    <Input value={bcc} onChange={(event) => setBcc(event.target.value)} aria-label="Bcc" />
                  </dd>
                </div>
              </>
            ) : (
              <>
                {outreach.cc ? <HeaderRow label="Cc" value={outreach.cc} /> : null}
                {outreach.bcc ? <HeaderRow label="Bcc" value={outreach.bcc} /> : null}
              </>
            )}
          </dl>
        </div>

        {/* --- subject --- */}
        {editing ? (
          <Field label="Subject" htmlFor="subject">
            <Input
              id="subject"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
            />
          </Field>
        ) : (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-subtle">Subject</p>
            <p className="mt-0.5 text-base font-medium text-foreground">
              {outreach.subject ?? "—"}
            </p>
          </div>
        )}

        {/* --- body --- */}
        {editing ? (
          <Field label="Body" htmlFor="body">
            <Textarea
              id="body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              className="min-h-72 font-sans"
            />
          </Field>
        ) : (
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              {outreach.body ?? "—"}
            </p>
          </div>
        )}

        {/* --- regeneration controls --- */}
        {!locked && !editing ? (
          <div className="flex flex-wrap items-end gap-3 border-t border-border pt-4">
            <Field label="Tone" htmlFor="tone" className="w-40">
              <Select
                id="tone"
                value={tone}
                onChange={(event) => setTone(event.target.value as OutreachTone)}
              >
                {TONES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Length" htmlFor="length" className="w-44">
              <Select
                id="length"
                value={length}
                onChange={(event) => setLength(event.target.value as MessageLength)}
              >
                {LENGTHS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Button
              variant="secondary"
              onClick={() => onRegenerate({ tone, message_length: length })}
              loading={regenerating}
            >
              <Sparkles /> Regenerate
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function HeaderRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-12 shrink-0 text-xs uppercase tracking-wide text-subtle">{label}</dt>
      <dd className="min-w-0 break-all text-muted">{value}</dd>
    </div>
  );
}
