"use client";

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";
import { pct } from "@/lib/mock-data";

type NewsSignal = {
  headline: string;
  sentiment_score: number;
  volume_score: number;
  sources_count: number;
};

type ExplainerResponse = {
  slug: string;
  model_prob: number;
  market_implied: number;
  edge: number;
  edge_direction: string;
  confidence_label: string;
  news_signals: NewsSignal[];
  trade_rationale: string;
  provisional: boolean;
  paper_trading_only: boolean;
};

type AITakePanelProps = {
  slug: string;
  className?: string;
};

export function AITakePanel({ slug, className }: AITakePanelProps) {
  const [open, setOpen] = useState(true);
  const [data, setData] = useState<ExplainerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug || !API_BASE) {
      return;
    }

    let cancelled = false;
    fetch(`${API_BASE}/api/v1/markets/${encodeURIComponent(slug)}/explain`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to load AI take");
        }
        return response.json() as Promise<ExplainerResponse>;
      })
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setError("AI advisor unavailable.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (error) {
    return (
      <section className={cn("rounded-2xl border border-border bg-surface p-4", className)}>
        <p className="text-sm text-muted">{error}</p>
      </section>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <section className={cn("rounded-2xl border border-border bg-surface", className)}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-black uppercase tracking-wide text-text">AI Take</span>
        <span className="text-xs text-muted">{open ? "Hide" : "Show"}</span>
      </button>

      {open ? (
        <div className="space-y-4 border-t border-border px-4 py-4">
          {data.provisional ? (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-200">
              Provisional — model not yet CLV-validated
            </p>
          ) : null}

          <div className="space-y-2">
            <div>
              <div className="mb-1 flex justify-between text-[11px] uppercase tracking-wide text-muted">
                <span>Model</span>
                <span>{pct(data.model_prob)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: `${Math.round(data.model_prob * 100)}%` }}
                />
              </div>
            </div>
            <div>
              <div className="mb-1 flex justify-between text-[11px] uppercase tracking-wide text-muted">
                <span>Market</span>
                <span>{pct(data.market_implied)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.round(data.market_implied * 100)}%` }}
                />
              </div>
            </div>
          </div>

          <p className="text-sm leading-relaxed text-text">{data.trade_rationale}</p>
          <p className="text-xs text-muted">
            Confidence: <span className="font-semibold text-text">{data.confidence_label}</span>{" "}
            · Edge {data.edge >= 0 ? "+" : ""}
            {(data.edge * 100).toFixed(1)}%
          </p>

          {data.news_signals.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {data.news_signals.map((signal) => (
                <span
                  key={signal.headline}
                  className="rounded-full border border-border bg-surface-2 px-2.5 py-1 text-[11px] text-muted"
                >
                  {signal.headline.slice(0, 72)}
                  {signal.headline.length > 72 ? "…" : ""}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted">News signals loading in background…</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
