"use client";

import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import useSWR from "swr";

import { PageHeader } from "@/components/domain/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { humanize } from "@/lib/format";

export default function SettingsPage() {
  const { data, error, isLoading, mutate } = useSWR("status", api.status, {
    refreshInterval: 30_000,
  });

  return (
    <>
      <PageHeader
        title="Settings"
        description="Configuration comes from environment variables. Values shown here never include credentials."
        actions={
          <Button variant="secondary" onClick={() => mutate()} loading={isLoading}>
            <RefreshCw /> Re-check
          </Button>
        }
      />

      {error ? (
        <Card>
          <ErrorState
            title="Cannot reach the backend"
            message={error.message}
            onRetry={() => mutate()}
          />
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <Card>
            <CardHeader>
              <CardTitle>Services</CardTitle>
              {data ? (
                <Badge tone={data.healthy ? "success" : "danger"}>
                  {data.healthy ? "All required services connected" : "Attention required"}
                </Badge>
              ) : null}
            </CardHeader>
            {isLoading && !data ? (
              <CardContent className="space-y-3">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-14 w-full" />
                ))}
              </CardContent>
            ) : (
              <ul className="divide-y divide-border">
                {data?.components.map((component) => (
                  <li
                    key={component.name}
                    className="flex items-start gap-3 px-5 py-4"
                  >
                    {component.connected ? (
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
                    ) : (
                      <XCircle
                        className={`mt-0.5 size-4 shrink-0 ${
                          component.optional ? "text-subtle" : "text-danger"
                        }`}
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-foreground">{component.name}</p>
                        <Badge tone="neutral">{component.provider}</Badge>
                        {component.optional ? <Badge tone="neutral">Optional</Badge> : null}
                      </div>
                      <p className="mt-1 text-sm text-muted">
                        {component.detail ??
                          (component.connected ? "Connected" : "Not connected")}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="h-fit">
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
              {data ? <Badge>{data.environment}</Badge> : null}
            </CardHeader>
            <CardContent>
              {isLoading && !data ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-5 w-full" />
                  ))}
                </div>
              ) : (
                <dl className="space-y-3">
                  {Object.entries(data?.configuration ?? {}).map(([key, value]) => (
                    <div key={key} className="flex flex-wrap items-baseline justify-between gap-2">
                      <dt className="text-xs text-muted">{humanize(key)}</dt>
                      <dd className="font-mono text-xs text-foreground">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <p className="mt-5 border-t border-border pt-4 text-xs text-subtle">
                To change any of these, edit <code className="font-mono">.env</code> at the
                project root and restart the backend.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
