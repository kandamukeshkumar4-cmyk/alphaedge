"use client";

import "./globals.css";
import { RouteError } from "@/components/RouteError";

// Global error boundary (Loop V13 U01 / V67 L3). Replaces the root layout when
// the layout itself throws, so it must render its own <html>/<body>. Never
// renders error.message/stack — RouteError only surfaces an optional digest.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" style={{ colorScheme: "dark" }}>
      <body className="min-h-screen bg-bg font-sans text-text">
        <RouteError
          error={error}
          reset={reset}
          title="AlphaEdge hit a hard error"
          description="The app shell failed to render. Your paper-trading account is safe. Try again, or return home — internals are not shown here."
        />
      </body>
    </html>
  );
}
