import type { Metadata } from "next";
import Link from "next/link";

import { pageMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = pageMetadata({
  title: "Page not found",
  description: "This AlphaEdge page does not exist. Head back home or browse paper markets.",
  path: "/404",
  noIndex: true,
});

/**
 * Loop V67 (L3) — branded 404 with navigation back. Never invents market data.
 */
export default function NotFound() {
  return (
    <main
      data-testid="not-found"
      className="mx-auto flex min-h-[60vh] max-w-[560px] flex-col items-center justify-center px-4 py-12 text-center"
    >
      <p className="font-mono text-xs font-bold uppercase tracking-[0.16em] text-primary">
        404 · Not found
      </p>
      <div className="mt-4 flex h-12 w-12 items-center justify-center rounded-full border border-border bg-surface-2 text-lg font-black text-primary">
        ?
      </div>
      <h1 className="mt-5 text-xl font-black tracking-tight text-text sm:text-2xl">
        This page does not exist
      </h1>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
        The route may have moved, or the link is wrong. AlphaEdge will not invent markets or scores
        to fill the gap — pick a real destination below.
      </p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-[0_0_16px_rgba(45,212,191,0.25)] transition hover:brightness-110"
        >
          Back home
        </Link>
        <Link
          href="/markets"
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-bold text-muted transition hover:border-border-light hover:text-text"
        >
          Browse markets
        </Link>
        <Link
          href="/about"
          className="rounded-lg border border-border bg-surface px-4 py-2 text-sm font-bold text-muted transition hover:border-border-light hover:text-text"
        >
          About
        </Link>
      </div>
    </main>
  );
}
