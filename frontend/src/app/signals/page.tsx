"use client";

import { useEffect, useMemo, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { InstabilityPanel } from "@/components/InstabilityPanel";
import { fetchSignalsDashboard } from "@/lib/signals-dashboard-api";
import { buildSignalsDashboardView } from "@/lib/signals-dashboard-view-model";

type Notice = {
  tone: "error" | "muted";
  text: string;
};

export default function SignalsPage() {
  const [notice, setNotice] = useState<Notice | null>(null);
  const [loading, setLoading] = useState(false);
  const [dashboard, setDashboard] = useState<Awaited<ReturnType<typeof fetchSignalsDashboard>>>(null);

  const view = useMemo(() => buildSignalsDashboardView(dashboard), [dashboard]);
  const apiConfigured = Boolean(API_BASE);

  useEffect(() => {
    if (!apiConfigured) {
      setNotice({
        tone: "muted",
        text: "Set NEXT_PUBLIC_API_URL to load live signal and CLV data.",
      });
      return;
    }
    void loadDashboard();
  }, [apiConfigured]);

  async function loadDashboard() {
    setLoading(true);
    setNotice(null);
    try {
      const next = await fetchSignalsDashboard();
      setDashboard(next);
    } catch (error) {
      setNotice({
        tone: "error",
        text: error instanceof Error ? error.message : "Failed to load signals dashboard.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-5">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">
            Phase 6
          </p>
          <h1 className="mt-1 text-3xl font-black tracking-tight text-text">
            Signals &amp; CLV Track Record
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Live arb, dutch, smart-money, and forecast signals with honest CLV
            reconciliation. FanDuel remains manual capture only in the extension.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadDashboard()}
          disabled={!apiConfigured || loading}
          className="h-10 rounded-xl border border-border px-4 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

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

      <InstabilityPanel />

      <section className="mb-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-black text-text">Signal feed</h2>
          <span className="text-xs text-muted">{view.signalCards.length} signals</span>
        </div>
        {view.signalCards.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-10 text-center text-sm text-muted">
            No signals detected yet. Headline-eligible arb, dutch, and forecast signals appear here.
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
                    {card.isEdge ? "Edge" : "Blocked"}
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
                    <dd className="font-mono font-bold text-text">{card.sampleSize}</dd>
                  </div>
                </dl>
                {card.provisional ? (
                  <p className="mt-3 rounded-lg bg-gold/10 px-3 py-2 text-xs font-semibold text-gold">
                    Provisional — N &lt; 30 resolved
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
                    No resolved CLV records yet.
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
        <p
          className={cn(
            "mt-6 rounded-xl px-4 py-3 text-sm",
            notice.tone === "error" ? "bg-danger/10 text-danger" : "bg-surface-2 text-muted",
          )}
        >
          {notice.text}
        </p>
      ) : null}

      <footer className="mt-8 rounded-xl border border-border bg-surface-2 px-4 py-3 text-xs font-semibold text-muted">
        {view.disclaimer}
      </footer>
    </main>
  );
}
