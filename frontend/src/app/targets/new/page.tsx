"use client";

import { Eye, Save, X } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { PageHeader } from "@/components/domain/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { InlineError, Skeleton } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import type { TargetInput } from "@/lib/types";

const COMPANY_SIZES = [
  { value: "any", label: "Any size" },
  { value: "1-10", label: "1–10 employees" },
  { value: "11-50", label: "11–50 employees" },
  { value: "51-200", label: "51–200 employees" },
  { value: "201-500", label: "201–500 employees" },
  { value: "501-1000", label: "501–1000 employees" },
  { value: "1000+", label: "1000+ employees" },
];

export default function NewTargetPage() {
  const router = useRouter();

  const [name, setName] = React.useState("");
  const [nameTouched, setNameTouched] = React.useState(false);
  const [industry, setIndustry] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [country, setCountry] = React.useState("");
  const [companySize, setCompanySize] = React.useState("any");
  const [keywords, setKeywords] = React.useState<string[]>([]);
  const [keywordDraft, setKeywordDraft] = React.useState("");
  const [context, setContext] = React.useState("");

  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({});

  const [preview, setPreview] = React.useState<string[] | null>(null);
  const [previewing, setPreviewing] = React.useState(false);

  // The name defaults to "Industry — Location" until the user edits it.
  React.useEffect(() => {
    if (nameTouched) return;
    const parts = [industry.trim(), location.trim()].filter(Boolean);
    setName(parts.join(" — "));
  }, [industry, location, nameTouched]);

  const payload: TargetInput = {
    name: name.trim(),
    industry: industry.trim(),
    location: location.trim() || null,
    country: country.trim() || null,
    company_size: companySize === "any" ? null : companySize,
    keywords,
    search_context: context.trim() || null,
  };

  const canSubmit = payload.name.length >= 2 && payload.industry.length >= 2;

  function addKeyword(raw: string) {
    const parts = raw
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length === 0) return;
    setKeywords((current) => {
      const next = [...current];
      for (const part of parts) {
        if (!next.some((item) => item.toLowerCase() === part.toLowerCase())) next.push(part);
      }
      return next.slice(0, 25);
    });
    setKeywordDraft("");
  }

  function onKeywordKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addKeyword(keywordDraft);
    } else if (event.key === "Backspace" && !keywordDraft) {
      setKeywords((current) => current.slice(0, -1));
    }
  }

  async function showPreview() {
    setPreviewing(true);
    setError(null);
    try {
      const result = await api.previewQueries(payload);
      setPreview(result.queries);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate a preview.");
    } finally {
      setPreviewing(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      const target = await api.createTarget(payload);
      router.push(`/targets/${target.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        setFieldErrors(extractFieldErrors(err));
      } else {
        setError("Could not save the target.");
      }
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="New target"
        description="Describe the kind of company to look for. Every field is free text — any industry and location is supported."
        backHref="/targets"
        backLabel="Targets"
      />

      <form onSubmit={submit} className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Target definition</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <Field
                label="Industry"
                htmlFor="industry"
                required
                hint="For example: Jewellery, BFSI, Hospitality, Renewable energy."
                error={fieldErrors.industry}
              >
                <Input
                  id="industry"
                  value={industry}
                  onChange={(event) => setIndustry(event.target.value)}
                  placeholder="Jewellery"
                  autoComplete="off"
                  required
                />
              </Field>

              <div className="grid gap-5 sm:grid-cols-2">
                <Field
                  label="Location"
                  htmlFor="location"
                  hint="City or region."
                  error={fieldErrors.location}
                >
                  <Input
                    id="location"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    placeholder="Indore"
                    autoComplete="off"
                  />
                </Field>
                <Field label="Country / region" htmlFor="country" error={fieldErrors.country}>
                  <Input
                    id="country"
                    value={country}
                    onChange={(event) => setCountry(event.target.value)}
                    placeholder="India"
                    autoComplete="off"
                  />
                </Field>
              </div>

              <Field
                label="Target name"
                htmlFor="name"
                required
                hint="Defaults to the industry and location; edit it if you prefer."
                error={fieldErrors.name}
              >
                <Input
                  id="name"
                  value={name}
                  onChange={(event) => {
                    setNameTouched(true);
                    setName(event.target.value);
                  }}
                  placeholder="Jewellery — Indore"
                  required
                  minLength={2}
                />
              </Field>

              <Field
                label="Company size"
                htmlFor="company_size"
                hint="Recorded on the target. Phase 1 does not filter search results by size."
              >
                <Select
                  id="company_size"
                  value={companySize}
                  onChange={(event) => setCompanySize(event.target.value)}
                >
                  {COMPANY_SIZES.map((size) => (
                    <option key={size.value} value={size.value}>
                      {size.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Search inputs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <Field
                label="Keywords"
                htmlFor="keywords"
                hint="Press Enter or comma to add. Each keyword produces its own search queries."
              >
                <div className="rounded-lg border border-border-strong bg-surface px-2 py-2">
                  {keywords.length > 0 ? (
                    <ul className="mb-2 flex flex-wrap gap-1.5">
                      {keywords.map((keyword) => (
                        <li key={keyword}>
                          <Badge tone="accent" className="pr-1">
                            {keyword}
                            <button
                              type="button"
                              onClick={() =>
                                setKeywords((current) =>
                                  current.filter((item) => item !== keyword),
                                )
                              }
                              className="ml-0.5 rounded-full p-0.5 hover:bg-accent/15"
                              aria-label={`Remove keyword ${keyword}`}
                            >
                              <X className="size-3" />
                            </button>
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <input
                    id="keywords"
                    value={keywordDraft}
                    onChange={(event) => setKeywordDraft(event.target.value)}
                    onKeyDown={onKeywordKeyDown}
                    onBlur={() => addKeyword(keywordDraft)}
                    placeholder={keywords.length ? "Add another…" : "jewellery stores"}
                    className="w-full bg-transparent px-1 py-1 text-sm outline-none placeholder:text-subtle"
                    autoComplete="off"
                  />
                </div>
              </Field>

              <Field
                label="Additional search context"
                htmlFor="context"
                hint="Optional free text appended to the primary query, e.g. “retail chain”."
              >
                <Textarea
                  id="context"
                  value={context}
                  onChange={(event) => setContext(event.target.value)}
                  placeholder="Retail chains with multiple showrooms"
                />
              </Field>
            </CardContent>
          </Card>

          {error ? <InlineError message={error} /> : null}

          <div className="flex flex-wrap gap-2">
            <Button type="submit" loading={saving} disabled={!canSubmit}>
              <Save /> Save target
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={showPreview}
              loading={previewing}
              disabled={!payload.industry}
            >
              <Eye /> Preview queries
            </Button>
          </div>
        </div>

        <aside className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Generated search queries</CardTitle>
            </CardHeader>
            <CardContent>
              {previewing ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <Skeleton key={index} className="h-6 w-full" />
                  ))}
                </div>
              ) : preview ? (
                preview.length > 0 ? (
                  <ol className="space-y-2">
                    {preview.map((query, index) => (
                      <li
                        key={query}
                        className="flex gap-2 rounded-md bg-surface-muted px-2.5 py-1.5 font-mono text-xs text-foreground"
                      >
                        <span className="text-subtle">{index + 1}.</span>
                        <span className="break-words">{query}</span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-muted">
                    No queries could be generated. Add an industry or a keyword.
                  </p>
                )
              ) : (
                <p className="text-sm text-muted">
                  Queries are generated from the fields on the left. Preview them before saving
                  to check the wording that will be sent to the search provider.
                </p>
              )}
            </CardContent>
          </Card>
        </aside>
      </form>
    </>
  );
}

/** Maps FastAPI's validation payload onto individual form fields. */
function extractFieldErrors(error: ApiError): Record<string, string> {
  const errors = (error.details as { errors?: { loc?: unknown[]; msg?: string }[] })?.errors;
  if (!Array.isArray(errors)) return {};
  const mapped: Record<string, string> = {};
  for (const item of errors) {
    const field = item.loc?.[item.loc.length - 1];
    if (typeof field === "string" && item.msg) mapped[field] = item.msg;
  }
  return mapped;
}
