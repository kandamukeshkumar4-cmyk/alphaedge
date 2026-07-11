"use client";

import "./globals.css";
import { RouteError } from "@/components/RouteError";

// Global error boundary (Loop V13 U01). Replaces the root layout when the
// layout itself throws, so it must render its own <html>/<body>. Imports
// globals.css so the Quest tokens are present even outside the normal layout.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg font-sans text-text">
        <RouteError error={error} reset={reset} />
      </body>
    </html>
  );
}
