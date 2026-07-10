"use client";

import { useEffect, useState } from "react";
import { fetchMemories, type AgentMemoryRow } from "@/lib/alphaedge-api";
import { pct } from "@/lib/mock-data";

/**
 * loop6 — "Similar past markets" card on the market detail view. Fed by the
 * agent-memory feed (GET /api/v1/memories, loop3), filtered to the same
 * category. Shows how the agent's past forecasts scored: question, resolved
 * outcome, model-vs-market probability at close, and Brier per row.
 *
 * Empty feed is an honest owner-blocked state (prod admin resolve), not a
 * fetch failure — never fabricate rows.
 */
export function SimilarPastMarkets({
  category,
  currentSlug,
}: {
  category: string;
  currentSlug: string;
}) {
  const [rows, setRows] = useState<AgentMemoryRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let dead = false;
    void fetchMemories(category, 8).then((items) => {
      if (dead) return;
      setRows(items.filter((m) => m.market_slug !== currentSlug));
      setLoaded(true);
    });
    return () => {
      dead = true;
    };
  }, [category, currentSlug]);

  return (
    <SimilarPastMarketsView category={category} rows={rows} loaded={loaded} />
  );
}

/**
 * Pure presentational view — takes already-fetched, already-filtered rows so it
 * can be rendered/tested without a network.
 */
export function SimilarPastMarketsView({
  category,
  rows,
  loaded = true,
}: {
  category: string;
  rows: AgentMemoryRow[];
  /** When true and rows empty, show honest owner-blocked empty (not a crash). */
  loaded?: boolean;
}) {
  if (!loaded) return null;

  if (rows.length === 0) {
    return (
      <section className="rounded-2xl border border-dashed border-border bg-surface p-4">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">
          Similar past markets
        </h2>
        <p className="mt-2 text-sm text-muted">
          No agent memories yet — appears after a seed market is resolved with the
          prod admin key (owner action).
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-4">
      <h2 className="text-sm font-bold uppercase tracking-wide text-muted">
        Similar past markets
      </h2>
      <p className="mt-1 text-xs text-muted">
        How the agent&apos;s past {category} forecasts resolved.
      </p>
      <ul className="mt-3 space-y-2">
        {rows.map((m) => (
          <li key={m.id} className="rounded-xl border border-border bg-bg/40 p-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-medium text-text">{m.question}</span>
              <span
                className={
                  m.outcome === "YES"
                    ? "shrink-0 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 font-mono text-[11px] font-bold text-primary"
                    : "shrink-0 rounded-full border border-danger/40 bg-danger/10 px-2 py-0.5 font-mono text-[11px] font-bold text-danger"
                }
              >
                {m.outcome}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-muted">
              {typeof m.model_prob_at_close === "number" ? (
                <span>
                  model <span className="text-accent">{pct(m.model_prob_at_close)}</span>
                </span>
              ) : null}
              {typeof m.market_prob_at_close === "number" ? (
                <span>
                  market <span className="text-text">{pct(m.market_prob_at_close)}</span>
                </span>
              ) : null}
              {typeof m.brier === "number" ? (
                <span>
                  Brier <span className="text-text">{m.brier.toFixed(4)}</span>
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
