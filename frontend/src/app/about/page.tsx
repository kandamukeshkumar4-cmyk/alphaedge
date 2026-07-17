import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader, PageShell, Panel } from "@/components/ui/kit";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";

export const metadata: Metadata = {
  title: "About — AlphaEdge",
  description:
    "What AlphaEdge is: a paper-trading prediction research platform with simulated funds, locked forecasts, and public proof — not financial advice.",
};

/**
 * Loop V67 (L1) — public About page. Honest product story for a stranger
 * arriving from a link: paper-only research, how forecasts lock/score, and a
 * path to the live proof dashboard. Reuses the exact backend disclaimer.
 */
export default function AboutPage() {
  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Paper-trading research"
        title="About AlphaEdge"
        subtitle="A prediction-market research platform for sports and election markets. Simulated funds only — no real-money execution, not financial advice."
      />

      <div className="space-y-5">
        <Panel title="What this is">
          <p className="text-sm leading-relaxed text-muted" data-testid="paper-trading-disclaimer">
            {PAPER_TRADING_DISCLAIMER}
          </p>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed text-muted">
            <li>
              AlphaEdge is a <strong className="text-text">paper-trading prediction research
              platform</strong> — you can explore markets, lock model forecasts, and track
              simulated portfolios.
            </li>
            <li>
              All balances and fills use <strong className="text-text">simulated funds</strong>.
              There is no cash funding, payment rail, or live exchange execution.
            </li>
            <li>
              Content here is for research and portfolio demonstration only —{" "}
              <strong className="text-text">not financial advice</strong> and not a promise of
              returns.
            </li>
          </ul>
        </Panel>

        <Panel title="How forecasts are locked and scored">
          <ol className="list-decimal space-y-3 pl-5 text-sm leading-relaxed text-muted">
            <li>
              Before a market locks, the model may show a live estimate. That estimate is not a
              scored call until it is locked.
            </li>
            <li>
              At lock time the platform records a <strong className="text-text">locked forecast</strong>{" "}
              — a frozen probability and lineage for the market. Later model refreshes do not rewrite
              that locked call.
            </li>
            <li>
              After the market resolves, the locked forecast is graded with standard probabilistic
              metrics (including Brier score) so accuracy can be compared honestly over time.
            </li>
            <li>
              Provisional or unvalidated model outputs are labeled as such — AlphaEdge does not
              invent scores or hide “not yet measured” states.
            </li>
          </ol>
        </Panel>

        <Panel title="Live proof">
          <p className="text-sm leading-relaxed text-muted">
            Calibration, model registry, and evaluation aggregates live on the public proof
            dashboard. Open it when you want the measured track record — not marketing copy.
          </p>
          <p className="mt-4">
            <Link
              href="/eval"
              className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-bg shadow-[0_0_16px_rgba(45,212,191,0.25)] transition hover:brightness-110"
            >
              Open /eval proof dashboard
            </Link>
          </p>
        </Panel>

        <p className="text-center text-xs text-muted-2">
          Also see{" "}
          <Link href="/terms" className="font-semibold text-primary hover:underline">
            Terms &amp; disclaimer
          </Link>
          .
        </p>
      </div>
    </PageShell>
  );
}
