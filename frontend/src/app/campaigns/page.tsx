"use client";

import { Layers, Plus, X } from "lucide-react";
import * as React from "react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, InlineError, TableSkeleton } from "@/components/ui/states";
import { RowLink, Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { formatDate, humanize } from "@/lib/format";
import type { MessageLength, OutreachTone } from "@/lib/types";

export default function CampaignsPage() {
  const campaigns = useSWR("campaigns", api.listCampaigns);
  const targets = useSWR("targets", api.listTargets);

  const [adding, setAdding] = React.useState(false);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [targetId, setTargetId] = React.useState("");
  const [tone, setTone] = React.useState<OutreachTone>("professional");
  const [length, setLength] = React.useState<MessageLength>("short");
  const [intervals, setIntervals] = React.useState("3, 7, 14");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const parsed = intervals
        .split(",")
        .map((part) => Number(part.trim()))
        .filter((value) => Number.isFinite(value) && value > 0);
      await api.createCampaign({
        name: name.trim(),
        description: description.trim() || null,
        target_id: targetId ? Number(targetId) : null,
        tone,
        message_length: length,
        follow_up_intervals: parsed.length ? parsed : [3, 7, 14],
      });
      setName("");
      setDescription("");
      setTargetId("");
      setIntervals("3, 7, 14");
      setAdding(false);
      await campaigns.mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the campaign.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Grouping for organisation and reporting. A campaign never sends anything on its own."
        actions={
          <Button variant={adding ? "secondary" : "primary"} onClick={() => setAdding((v) => !v)}>
            {adding ? <X /> : <Plus />}
            {adding ? "Cancel" : "New campaign"}
          </Button>
        }
      />

      {error ? <InlineError className="mb-4" message={error} /> : null}

      {adding ? (
        <Card className="mb-5">
          <CardHeader>
            <CardTitle>New campaign</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={create} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name" htmlFor="c-name" required>
                  <Input
                    id="c-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Jewellery — Indore growth outreach"
                  />
                </Field>
                <Field label="Target" htmlFor="c-target" hint="Optional link to a Phase 1 target.">
                  <Select
                    id="c-target"
                    value={targetId}
                    onChange={(event) => setTargetId(event.target.value)}
                  >
                    <option value="">No target</option>
                    {targets.data?.map((target) => (
                      <option key={target.id} value={target.id}>
                        {target.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <Field label="Description" htmlFor="c-description">
                <Textarea
                  id="c-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </Field>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Default tone" htmlFor="c-tone">
                  <Select
                    id="c-tone"
                    value={tone}
                    onChange={(event) => setTone(event.target.value as OutreachTone)}
                  >
                    <option value="professional">Professional</option>
                    <option value="conversational">Conversational</option>
                    <option value="direct">Direct</option>
                    <option value="warm">Warm</option>
                  </Select>
                </Field>
                <Field label="Default length" htmlFor="c-length">
                  <Select
                    id="c-length"
                    value={length}
                    onChange={(event) => setLength(event.target.value as MessageLength)}
                  >
                    <option value="short">Short</option>
                    <option value="medium">Medium</option>
                  </Select>
                </Field>
                <Field
                  label="Follow-up intervals"
                  htmlFor="c-intervals"
                  hint="Days after sending. Must increase."
                >
                  <Input
                    id="c-intervals"
                    value={intervals}
                    onChange={(event) => setIntervals(event.target.value)}
                    placeholder="3, 7, 14"
                  />
                </Field>
              </div>
              <Button type="submit" loading={saving} disabled={name.trim().length < 2}>
                Create campaign
              </Button>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        {campaigns.isLoading ? (
          <TableSkeleton columns={5} />
        ) : campaigns.error ? (
          <ErrorState message={campaigns.error.message} onRetry={() => campaigns.mutate()} />
        ) : !campaigns.data || campaigns.data.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No campaigns yet"
            description="Create one to group related outreach and set shared defaults."
          />
        ) : (
          <TableWrap>
            <Table className="min-w-[46rem]">
              <thead>
                <tr>
                  <Th>Campaign</Th>
                  <Th>Target</Th>
                  <Th>Status</Th>
                  <Th>Follow-ups</Th>
                  <Th>Created</Th>
                  <Th className="text-right">Outreach</Th>
                </tr>
              </thead>
              <tbody>
                {campaigns.data.map((campaign) => (
                  <Tr key={campaign.id}>
                    <Td>
                      <RowLink href={`/outreach?campaign_id=${campaign.id}`}>
                        {campaign.name}
                      </RowLink>
                      {campaign.description ? (
                        <p className="mt-0.5 max-w-sm truncate text-xs text-subtle">
                          {campaign.description}
                        </p>
                      ) : null}
                    </Td>
                    <Td className="text-muted">{campaign.target_name ?? "—"}</Td>
                    <Td>
                      <Badge tone={campaign.status === "active" ? "success" : "neutral"}>
                        {humanize(campaign.status)}
                      </Badge>
                    </Td>
                    <Td className="text-muted">
                      {campaign.follow_up_intervals.join(", ")} days
                    </Td>
                    <Td className="whitespace-nowrap text-muted">
                      {formatDate(campaign.created_at)}
                    </Td>
                    <Td className="text-right tabular-nums text-muted">
                      {campaign.outreach_total}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>
    </>
  );
}
