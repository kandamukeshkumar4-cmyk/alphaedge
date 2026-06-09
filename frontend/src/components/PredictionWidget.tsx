"use client";

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { cn } from "@/lib/cn";

type MarketPrediction = {
  slug: string;
  predicted_prob: number;
  confidence: number;
  edge: number;
  is_edge: boolean;
  reason: string;
  provisional: boolean;
  paper_trading_only: boolean;
};

type PredictionWidgetProps = {
  slug: string;
  className?: string;
};

export function PredictionWidget({ slug, className }: PredictionWidgetProps) {
  const [prediction, setPrediction] = useState<MarketPrediction | null>(null);

  useEffect(() => {
    if (!slug) {
      setPrediction(null);
      return;
    }

    let cancelled = false;

    fetch(`${API_BASE}/api/v1/markets/${encodeURIComponent(slug)}/prediction`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("prediction fetch failed");
        }
        return response.json() as Promise<MarketPrediction>;
      })
      .then((data) => {
        if (!cancelled) {
          setPrediction(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPrediction(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (!prediction) {
    return null;
  }

  const confidencePct = Math.round(prediction.confidence * 100);
  const modelPct = Math.round(prediction.predicted_prob * 100);

  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-bg/60 p-4",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-lg bg-gradient-to-br from-accent to-[#1B5FD0] font-mono text-[11px] font-black text-white">
          AI
        </span>
        <h3 className="text-sm font-black text-text">Market prediction</h3>
        {prediction.provisional ? (
          <span className="ml-auto rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-amber-300">
            Provisional — no closing line
          </span>
        ) : null}
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between text-xs text-muted">
          <span>AI Confidence</span>
          <span className="font-mono font-bold text-text">{confidencePct}%</span>
        </div>
        <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-border/80">
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent to-[#1B5FD0] transition-[width] duration-300"
            style={{ width: `${confidencePct}%` }}
            role="progressbar"
            aria-valuenow={confidencePct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="AI confidence"
          />
        </div>
      </div>

      <p className="mt-3 font-mono text-lg font-black text-accent">
        Model: {modelPct}% YES
      </p>
    </div>
  );
}
