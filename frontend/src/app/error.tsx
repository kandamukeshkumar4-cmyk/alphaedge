"use client";

import { RouteError } from "@/components/RouteError";

// Root App Router error boundary (Loop V13 U01). Catches render errors thrown
// anywhere in the page tree that a segment boundary did not, keeping the
// header/nav shell alive instead of blanking the whole app.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteError error={error} reset={reset} />;
}
