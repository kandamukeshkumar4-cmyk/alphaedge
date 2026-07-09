"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";
import {
  fetchArbOpportunities,
  type ArbOpportunitiesPage,
} from "@/lib/arb-api";
import { cn } from "@/lib/cn";
import { fetchSignalsDashboard } from "@/lib/signals-dashboard-api";
import { buildSignalsDashboardView } from "@/lib/signals-dashboard-view-model";
import { PageHeader, PageShell } from "@/components/ui/kit";

type Notice = {
  tone: "error" | "muted";
  text: string;
};

export default function SignalsPage() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const apiConfigured = hasLiveApi();
  const [loading, setLoading] = useState(apiConfigured);
  const [dashboard, setDashboard] = useState<Awaited<ReturnType<typeof fetchSignalsDashboard>>>(null);
  const [arb, setArb] = useState<ArbOpportunitiesPage | null>(null);

  const view = useMemo(() => buildSignalsDashboardView(dashboard), [dashboard]);

  async function loadDashboard() {
    const base = await ensureApiBase();
    if (!hasLiveApi(base)) {
      setNotice({
        tone: "muted",
        text: "Set NEXT_PUBLIC_API_URL to load live signal and CLV data.",
      });
      setLoading(false);
      return;
    }
    setLoading(true);
    setNotice(null);
    try {
      const [next, arbPage] = await Promise.all([
        fetchSignalsDashboard({ apiBase: base }),
        fetchArbOpportunities(8),
      ]);
      setDashboard(next);
      setArb(arbPage);
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : "Failed to load signals dashboard.";
      setNotice({
        tone: "error",
        text: `${detail} (${base || "same-origin"}) — showing last loaded data. Retry below.`,
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, [apiConfigured]);

  return (
    <PageShell width="medium">
      <PageHeader
        kicker="Signal intelligence"
        title="Signals & CLV track record"
        subtitle="Paper-trading alerts for price moves and forecasts. Edge only shows when there's enough history to back it up."
        actions={
          <button
            type="button"
            onClick={() => void loadDashboard()}
            disabled={!apiConfigured || loading}
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        }
      />

      <section className="mb-6 rounded-2xl border border-border bg-surface p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">
              Paper P&amp;L summary
            </p>
            <p className="mt-1 font-mono text-3xl font-black text-text">{view.paperPnlLabel}</p>
          </div>
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">Bets</p>
              <p className="font-mono text-lg font-bold text-text">{view.betCountLabel}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.08em] text-muted">Win rate</p>
              <p className="font-mono text-lg font-bold text-text">{view.winRateLabel}</p>
            </div>
          </div>
        </div>
        <p className="mt-3 text-xs font-semibold text-gold">{view.paperOnlyNote}</p>
      </section>

      {view.llmExplanation ? (
        <section className="mb-6 rounded-2xl border border-border bg-surface-2 p-4 text-sm text-text">
          <p>{view.llmExplanation}</p>
        </section>
      ) : null}

      <section className="mb-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-black text-text">Cross-market arb</h2>
          <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.06em] text-muted">
            Signal only / paper
          </span>
        </div>
        {!arb || arb.opportunities.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-center text-sm text-muted">
            No cross-platform arb signals right now
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {arb.opportunities.map((opp) => (
              <article
                key={opp.id}
                className={cn(
                  "rounded-2xl border border-border bg-surface p-4",
                  opp.stale && "opacity-60",
                )}
              >
                <p className="text-xs font-bold uppercase tracking-[0.06em] text-accent">
                  Polymarket ↔ Kalshi
                  {opp.stale ? " · Stale" : ""}
                </p>
                <p className="mt-1 text-sm font-bold text-text">{opp.pm_title}</p>
                <p className="text-xs text-muted">{opp.kalshi_title}</p>
                <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <dt className="text-[10px] font-bold uppercase text-muted">Edge</dt>
                    <dd className="font-mono font-bold text-text">{opp.theoretical_edge}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] font-bold uppercase text-muted">Match</dt>
                    <dd className="font-mono font-bold text-text">
                      {Math.round(opp.match_confidence * 100)}%
                    </dd>
                  </div>
                </dl>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <Link
                    href={`/markets/view?slug=${encodeURIComponent(opp.pm_market_id)}`}
                    className="font-semibold text-accent hover:underline"
                  >
                    PM market
                  </Link>
                  <Link
                    href={`/markets/view?slug=${encodeURIComponent(opp.kalshi_market_id)}`}
                    className="font-semibold text-accent hover:underline"
                  >
                    Kalshi market
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
        {arb?.note ? (
          <p className="mt-2 text-xs text-muted">{arb.note}</p>
        ) : null}
      </section>

      <section className="mb-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-black text-text">Signal feed</h2>
          <span className="text-xs text-muted">{view.signalCards.length} signals</span>
        </div>
        {loading && view.signalCards.length === 0 ? (
          <div className="grid gap-4 md:grid-cols-2" aria-hidden>
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="skeleton h-36 w-full rounded-2xl" />
            ))}
          </div>
        ) : view.signalCards.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
            No signals yet. When the system spots a move worth watching, it shows up here.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {view.signalCards.map((card) => (
              <article
                key={card.id}
                className="rounded-2xl border border-border bg-surface p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">
                      {card.signalTypeLabel}
                    </p>
                    <h3 className="mt-1 text-base font-bold text-text">{card.marketName}</h3>
                  </div>
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.06em]",
                      card.isEdge
                        ? "bg-primary/15 text-primary"
                        : "bg-surface-2 text-muted",
                    )}
                  >
                    {card.statusLabel}
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
                      Net edge
                    </dt>
                    <dd className="font-mono font-bold text-text">{card.impliedEdgeLabel}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
                      Sample
                    </dt>
                    <dd className="font-mono font-bold text-text">{card.sampleSizeLabel}</dd>
                  </div>
                </dl>
                {card.provisionalNote ? (
                  <p className="mt-3 rounded-lg bg-gold/10 px-3 py-2 text-xs font-semibold text-gold">
                    {card.provisionalNote}
                  </p>
                ) : null}
                {card.blockedLabel ? (
                  <p className="mt-3 text-xs font-semibold text-muted">{card.blockedLabel}</p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-black text-text">CLV track record</h2>
          <span className="text-xs text-muted">{view.clvRows.length} resolved</span>
        </div>
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-2 text-xs font-bold uppercase tracking-[0.06em] text-muted">
              <tr>
                <th className="px-4 py-3">Market</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Closing</th>
                <th className="px-4 py-3">CLV</th>
                <th className="px-4 py-3">Resolved</th>
              </tr>
            </thead>
            <tbody>
              {view.clvRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted">
                    No resolved track-record rows yet — they appear after markets settle.
                  </td>
                </tr>
              ) : (
                view.clvRows.map((row) => (
                  <tr key={`${row.market}-${row.resolvedAtLabel}`} className="border-t border-border/70">
                    <td className="px-4 py-3 font-semibold text-text">{row.market}</td>
                    <td className="px-4 py-3 font-mono">{row.modelProbLabel}</td>
                    <td className="px-4 py-3 font-mono">{row.closingProbLabel}</td>
                    <td
                      className={cn(
                        "px-4 py-3 font-mono font-bold",
                        row.clvLabel.startsWith("+")
                          ? "text-up"
                          : row.clvLabel.startsWith("-")
                            ? "text-danger"
                            : "text-text",
                      )}
                    >
                      {row.clvLabel}
                    </td>
                    <td className="px-4 py-3 text-muted">{row.resolvedAtLabel}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {notice ? (
        <div
          className={cn(
            "mt-6 rounded-xl px-4 py-3 text-sm",
            notice.tone === "error" ? "bg-danger/10 text-danger" : "bg-surface-2 text-muted",
          )}
        >
          <p>{notice.text}</p>
          {notice.tone === "error" ? (
            <button
              type="button"
              onClick={() => void loadDashboard()}
              disabled={loading}
              className="mt-2 text-xs font-bold underline hover:no-underline disabled:opacity-50"
            >
              Retry now
            </button>
          ) : null}
        </div>
      ) : null}

      <footer className="mt-8 rounded-xl border border-border bg-surface-2 px-4 py-3 text-xs font-semibold text-muted">
        {view.disclaimer}
      </footer>
    </PageShell>
  );
}
