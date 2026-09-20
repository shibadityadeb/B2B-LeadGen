"use client";

import { Card } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Card>
      <ErrorState
        title="Something went wrong"
        message={error.message || "An unexpected error occurred while rendering this page."}
        onRetry={reset}
      />
    </Card>
  );
}
