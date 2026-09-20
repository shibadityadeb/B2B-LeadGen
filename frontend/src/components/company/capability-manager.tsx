"use client";

import { Plus, X } from "lucide-react";
import * as React from "react";
import useSWR from "swr";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { ErrorState, InlineError, Skeleton } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import type { UbmCapability } from "@/lib/types";

/**
 * Capabilities are configuration, not code. Editing one here changes what the
 * matching engine produces on the next research run — no deploy involved.
 */
export function CapabilityManager() {
  const capabilities = useSWR("capabilities", api.listCapabilities);
  const signalTypes = useSWR("signal-types", api.listSignalTypes);

  const [adding, setAdding] = React.useState(false);
  const [busyId, setBusyId] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [selectedTypes, setSelectedTypes] = React.useState<string[]>([]);
  const [saving, setSaving] = React.useState(false);

  async function toggleActive(capability: UbmCapability) {
    setBusyId(capability.id);
    setError(null);
    try {
      await api.updateCapability(capability.id, { active: !capability.active });
      await capabilities.mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the capability.");
    } finally {
      setBusyId(null);
    }
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.createCapability({
        name: name.trim(),
        description: description.trim(),
        category: category.trim() || null,
        signal_types: selectedTypes,
      });
      setName("");
      setDescription("");
      setCategory("");
      setSelectedTypes([]);
      setAdding(false);
      await capabilities.mutate();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the capability.");
    } finally {
      setSaving(false);
    }
  }

  const canSubmit = name.trim().length >= 2 && description.trim().length >= 10 && selectedTypes.length > 0;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>UBM capabilities</CardTitle>
          <p className="mt-0.5 text-xs text-subtle">
            Each capability is matched to the business signals it responds to — never to an
            industry.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setAdding((value) => !value)}>
          {adding ? <X /> : <Plus />}
          {adding ? "Cancel" : "Add capability"}
        </Button>
      </CardHeader>

      {error ? (
        <CardContent>
          <InlineError message={error} />
        </CardContent>
      ) : null}

      {adding ? (
        <CardContent className="border-b border-border bg-surface-muted/40">
          <form onSubmit={create} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name" htmlFor="cap-name" required>
                <Input
                  id="cap-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Retail Media Networks"
                />
              </Field>
              <Field label="Category" htmlFor="cap-category">
                <Input
                  id="cap-category"
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  placeholder="Digital"
                />
              </Field>
            </div>
            <Field label="Description" htmlFor="cap-description" required>
              <Textarea
                id="cap-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What this capability delivers for a client."
              />
            </Field>
            <Field
              label="Relevant business signals"
              required
              hint="This capability becomes a candidate when a company shows one of these signals."
            >
              <div className="flex flex-wrap gap-1.5">
                {signalTypes.data?.map((option) => {
                  const active = selectedTypes.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() =>
                        setSelectedTypes((current) =>
                          current.includes(option.value)
                            ? current.filter((item) => item !== option.value)
                            : [...current, option.value],
                        )
                      }
                      aria-pressed={active}
                      className={
                        active
                          ? "rounded-full border border-accent-border bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent"
                          : "rounded-full border border-border bg-surface px-2.5 py-1 text-xs text-muted hover:border-border-strong"
                      }
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </Field>
            <Button type="submit" size="sm" loading={saving} disabled={!canSubmit}>
              Create capability
            </Button>
          </form>
        </CardContent>
      ) : null}

      {capabilities.isLoading ? (
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-16 w-full" />
          ))}
        </CardContent>
      ) : capabilities.error ? (
        <ErrorState message={capabilities.error.message} onRetry={() => capabilities.mutate()} />
      ) : (
        <ul className="divide-y divide-border">
          {capabilities.data?.map((capability) => (
            <li key={capability.id} className="px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-foreground">{capability.name}</p>
                    {capability.category ? (
                      <Badge tone="neutral">{capability.category}</Badge>
                    ) : null}
                    {!capability.active ? <Badge tone="warning">Inactive</Badge> : null}
                    {!capability.is_seed ? <Badge tone="accent">Custom</Badge> : null}
                  </div>
                  <p className="mt-1 text-sm text-muted">{capability.description}</p>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {capability.signal_types.map((type) => (
                      <li key={type}>
                        <Badge tone="neutral">
                          {signalTypes.data?.find((item) => item.value === type)?.label ?? type}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busyId === capability.id}
                  onClick={() => toggleActive(capability)}
                >
                  {capability.active ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
