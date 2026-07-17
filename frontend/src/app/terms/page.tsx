import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader, PageShell, Panel } from "@/components/ui/kit";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";

export const metadata: Metadata = {
  title: "Terms & disclaimer — AlphaEdge",
  description:
    "Paper-trading terms and disclaimer for AlphaEdge. Simulated funds only; not financial advice; no real-money execution.",
};

/**
 * Loop V67 (L1) — public Terms / disclaimer page. Carries the exact
 * PAPER_TRADING_DISCLAIMER language and clear scope limits for a public launch.
 */
export default function TermsPage() {
  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Legal"
        title="Terms & disclaimer"
        subtitle="Scope of the AlphaEdge paper-trading simulation. Read this before using the product."
      />

      <div className="space-y-5">
        <Panel title="Paper-trading disclaimer">
          <p
            className="text-sm leading-relaxed text-muted"
            data-testid="paper-trading-disclaimer"
          >
            {PAPER_TRADING_DISCLAIMER}
          </p>
        </Panel>

        <Panel title="What AlphaEdge is not">
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-muted">
            <li>
              Not a broker, exchange, casino, or real-money prediction market. No real currency is
              deposited, withdrawn, or settled through this product.
            </li>
            <li>
              Not financial, investment, legal, or tax advice. Nothing on AlphaEdge is a
              recommendation to buy, sell, or hold any instrument.
            </li>
            <li>
              Not a guarantee of accuracy, edge, or returns. Model outputs and paper P&amp;L can be
              wrong, incomplete, or delayed.
            </li>
          </ul>
        </Panel>

        <Panel title="Simulated funds & research use">
          <p className="text-sm leading-relaxed text-muted">
            Balances, positions, fills, leaderboards, and pods use simulated funds for research and
            portfolio demonstration only. Orders — when available — travel through the paper risk
            path only. LLM and agent surfaces cannot submit raw live orders.
          </p>
        </Panel>

        <Panel title="Forecast locking & scoring">
          <p className="text-sm leading-relaxed text-muted">
            Locked forecasts are frozen at lock time and graded after resolution with probabilistic
            metrics such as Brier score. Unmeasured or provisional results are labeled honestly.
            Live aggregates and calibration appear on the{" "}
            <Link href="/eval" className="font-semibold text-primary hover:underline">
              /eval proof dashboard
            </Link>
            .
          </p>
        </Panel>

        <Panel title="Acceptable use">
          <p className="text-sm leading-relaxed text-muted">
            Use AlphaEdge for research, education, and paper portfolio practice. Do not attempt to
            circumvent paper-trading controls, scrape private admin surfaces, or represent AlphaEdge
            outputs as real-money trading results.
          </p>
        </Panel>

        <p className="text-center text-xs text-muted-2">
          Product overview:{" "}
          <Link href="/about" className="font-semibold text-primary hover:underline">
            About AlphaEdge
          </Link>
          .
        </p>
      </div>
    </PageShell>
  );
}
