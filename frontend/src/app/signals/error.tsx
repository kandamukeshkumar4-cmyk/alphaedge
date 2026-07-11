"use client";

import { RouteError } from "@/components/RouteError";

// Segment error boundary (Loop V13 U01) — a child throw here degrades to the
// shared Quest fallback instead of blanking the whole app.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError error={error} reset={reset} />;
}
