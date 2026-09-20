"use client";

import { AlertTriangle, CheckCircle2, Mail, ShieldCheck } from "lucide-react";
import { useSearchParams } from "next/navigation";
import * as React from "react";
import useSWR from "swr";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field, Input, Textarea } from "@/components/ui/input";
import { InlineError, Skeleton } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

/** Gmail connection state. Tokens live server-side and are never shown here. */
export function GmailSettings() {
  const searchParams = useSearchParams();
  const gmail = useSWR("gmail-status", api.gmailStatus);

  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = React.useState(false);

  // The OAuth callback returns the user here with a result flag.
  const callbackResult = searchParams.get("gmail");
  const callbackReason = searchParams.get("reason");

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const { authorization_url } = await api.gmailAuthorizeUrl();
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the Gmail connection.");
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      await api.gmailDisconnect();
      await gmail.mutate();
      setConfirmDisconnect(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not disconnect Gmail.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Gmail</CardTitle>
          <p className="mt-0.5 text-xs text-subtle">
            Used only to create drafts in your mailbox. The application cannot send mail.
          </p>
        </div>
        {gmail.data ? (
          <Badge tone={gmail.data.connected ? "success" : "neutral"}>
            {gmail.data.connected ? "Connected" : "Not connected"}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        {callbackResult === "connected" ? (
          <p className="flex items-center gap-2 rounded-lg border border-success/30 bg-success-soft px-3 py-2 text-sm text-success">
            <CheckCircle2 className="size-4" /> Gmail connected.
          </p>
        ) : null}
        {callbackResult === "error" ? (
          <InlineError
            message={`Gmail could not be connected${callbackReason ? ` (${callbackReason.replace(/_/g, " ")})` : ""}. Try again.`}
          />
        ) : null}
        {error ? <InlineError message={error} /> : null}

        {gmail.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : (
          <>
            {gmail.data?.detail ? (
              <p className="text-sm text-muted">{gmail.data.detail}</p>
            ) : null}

            {gmail.data?.account_email ? (
              <dl className="space-y-2 text-sm">
                <div className="flex gap-3">
                  <dt className="w-24 shrink-0 text-xs uppercase tracking-wide text-subtle">
                    Account
                  </dt>
                  <dd className="break-all text-foreground">{gmail.data.account_email}</dd>
                </div>
                {gmail.data.connected_at ? (
                  <div className="flex gap-3">
                    <dt className="w-24 shrink-0 text-xs uppercase tracking-wide text-subtle">
                      Connected
                    </dt>
                    <dd className="text-muted">{formatDateTime(gmail.data.connected_at)}</dd>
                  </div>
                ) : null}
                <div className="flex gap-3">
                  <dt className="w-24 shrink-0 text-xs uppercase tracking-wide text-subtle">
                    Access
                  </dt>
                  <dd className="text-muted">
                    <span className="inline-flex items-center gap-1.5">
                      <ShieldCheck className="size-3.5 text-success" />
                      Draft-only (gmail.compose)
                    </span>
                  </dd>
                </div>
              </dl>
            ) : null}

            {gmail.data?.needs_reauth && gmail.data?.configured ? (
              <p className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning-soft/50 px-3 py-2 text-sm text-muted">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
                The stored authorization is no longer valid. Reconnect to continue creating
                drafts.
              </p>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {gmail.data?.configured ? (
                <Button onClick={connect} loading={busy} variant={gmail.data.connected ? "secondary" : "primary"}>
                  <Mail /> {gmail.data.connected ? "Reconnect" : "Connect Gmail"}
                </Button>
              ) : null}
              {gmail.data?.connected ? (
                <Button variant="ghost" onClick={() => setConfirmDisconnect(true)}>
                  Disconnect
                </Button>
              ) : null}
            </div>
          </>
        )}
      </CardContent>

      <ConfirmDialog
        open={confirmDisconnect}
        loading={busy}
        title="Disconnect Gmail?"
        description="Stored credentials are deleted. Drafts already created stay in your mailbox, and no email is affected."
        confirmLabel="Disconnect"
        onCancel={() => setConfirmDisconnect(false)}
        onConfirm={disconnect}
      />
    </Card>
  );
}

/** The identity outreach is written from. Nothing is hardcoded to a person. */
export function SenderProfileSettings() {
  const profile = useSWR("sender-profile", api.getSenderProfile);

  const [name, setName] = React.useState("");
  const [role, setRole] = React.useState("");
  const [company, setCompany] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [website, setWebsite] = React.useState("");
  const [signature, setSignature] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!profile.data) return;
    setName(profile.data.name ?? "");
    setRole(profile.data.role ?? "");
    setCompany(profile.data.company ?? "");
    setEmail(profile.data.email ?? "");
    setWebsite(profile.data.website ?? "");
    setSignature(profile.data.signature ?? "");
  }, [profile.data]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.updateSenderProfile({
        name: name.trim(),
        role: role.trim() || null,
        company: company.trim(),
        email: email.trim() || null,
        website: website.trim() || null,
        signature: signature.trim() || null,
      });
      await profile.mutate();
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the sender profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Sender profile</CardTitle>
          <p className="mt-0.5 text-xs text-subtle">
            Used in the signature of every generated message.
          </p>
        </div>
      </CardHeader>
      <CardContent>
        {profile.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <form onSubmit={save} className="space-y-4">
            {error ? <InlineError message={error} /> : null}
            {saved ? (
              <p className="text-sm text-success">Sender profile saved.</p>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name" htmlFor="s-name" required>
                <Input id="s-name" value={name} onChange={(e) => setName(e.target.value)} />
              </Field>
              <Field label="Role" htmlFor="s-role">
                <Input
                  id="s-role"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  placeholder="Business Development"
                />
              </Field>
              <Field label="Company" htmlFor="s-company" required>
                <Input
                  id="s-company"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              </Field>
              <Field
                label="Email"
                htmlFor="s-email"
                hint="Shown in the preview. Drafts are created in the connected mailbox."
              >
                <Input
                  id="s-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Website" htmlFor="s-website">
              <Input id="s-website" value={website} onChange={(e) => setWebsite(e.target.value)} />
            </Field>
            <Field
              label="Signature"
              htmlFor="s-signature"
              hint="Leave blank to use a simple signature built from the fields above."
            >
              <Textarea
                id="s-signature"
                value={signature}
                onChange={(e) => setSignature(e.target.value)}
                placeholder={"Best,\nYour name\nUpshot Brand Media"}
              />
            </Field>
            <Button type="submit" loading={saving} disabled={name.trim().length < 2}>
              Save sender profile
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
