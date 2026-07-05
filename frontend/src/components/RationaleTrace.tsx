"use client";

/**
 * RationaleTrace — collapsible agent-graph step viewer for U03 DecisionCard.
 *
 * Renders each AgentTraceStep (data → news → prediction → risk → reasoning
 * → execute) as an expandable row. Clicking a row shows the key output fields
 * for that node so the user can see how the model arrived at its verdict.
 *
 * Data comes from GET /api/v1/markets/{slug}/agent-trace (new U03 endpoint).
 */

import { useState } from "react";
import { cn } from "@/lib/cn";

export type AgentTraceStep = {
  step_name: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
};

type Props = {
  steps: AgentTraceStep[];
  className?: string;
};

const STEP_LABELS: Record<string, { label: string; emoji: string }> = {
  data:       { label: "Data fetch",   emoji: "📥" },
  news:       { label: "News signal",  emoji: "📰" },
  prediction: { label: "Prediction",   emoji: "🔮" },
  risk:       { label: "Risk gate",    emoji: "🛡" },
  reasoning:  { label: "Reasoning",    emoji: "🧠" },
  execute:    { label: "Execute gate", emoji: "🔒" },
};

/** Picks the most reader-relevant fields from a step's output for display. */
function summariseStep(name: string, output: Record<string, unknown>): string {
  switch (name) {
    case "data": {
      const implied = output.features && typeof output.features === "object"
        ? (output.features as Record<string, unknown>).implied_yes
        : undefined;
      return implied !== undefined
        ? `Market implied: ${(Number(implied) * 100).toFixed(1)}%`
        : "Features loaded";
    }
    case "news": {
      const feat = output.features && typeof output.features === "object"
        ? output.features as Record<string, unknown>
        : {};
      const sentiment = feat.news_sentiment;
      const headline = feat.news_headline;
      if (sentiment !== undefined)
        return `Sentiment ${Number(sentiment) >= 0 ? "+" : ""}${Number(sentiment).toFixed(2)}${headline ? ` — "${String(headline).slice(0, 60)}"` : ""}`;
      return "No news signal cached";
    }
    case "prediction": {
      const prob = output.predicted_prob;
      const conf = output.confidence;
      if (prob !== undefined)
        return `Model: ${(Number(prob) * 100).toFixed(1)}%  conf ${(Number(conf) * 100).toFixed(0)}%`;
      return "Prediction unavailable";
    }
    case "risk": {
      const approved = output.approved;
      const errors = Array.isArray(output.errors) ? output.errors as string[] : [];
      if (approved) return "Risk gate: approved";
      return `Risk gate: blocked — ${errors[0] ?? "unknown reason"}`;
    }
    case "reasoning":
      return typeof output.reasoning === "string"
        ? String(output.reasoning).slice(0, 120)
        : "Reasoning computed";
    case "execute":
      return output.approved ? "Execution approved" : "Execution blocked by risk";
    default:
      return "Step complete";
  }
}

export function RationaleTrace({ steps, className }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (steps.length === 0) {
    return (
      <p className={cn("text-xs text-muted", className)}>
        No trace steps available.
      </p>
    );
  }

  return (
    <div className={cn("space-y-1", className)}>
      {steps.map((step, idx) => {
        const meta = STEP_LABELS[step.step_name] ?? { label: step.step_name, emoji: "·" };
        const isExpanded = expanded === step.step_name;
        const summary = summariseStep(step.step_name, step.output_data);
        const isLast = idx === steps.length - 1;

        return (
          <div key={step.step_name} className="relative">
            {/* Connector line */}
            {!isLast && (
              <span
                aria-hidden="true"
                className="absolute left-[13px] top-7 h-[calc(100%-4px)] w-px bg-border"
              />
            )}

            <button
              type="button"
              onClick={() => setExpanded(isExpanded ? null : step.step_name)}
              aria-expanded={isExpanded}
              className="relative flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition hover:bg-surface-2"
            >
              {/* Node icon */}
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-border bg-surface text-[11px]">
                {meta.emoji}
              </span>

              <span className="min-w-0 flex-1 pt-0.5">
                <span className="block text-xs font-bold text-text">
                  {meta.label}
                </span>
                <span className="mt-0.5 block truncate text-[11px] text-muted">
                  {summary}
                </span>
              </span>

              <span className="shrink-0 pt-0.5 text-[10px] text-muted-2">
                {isExpanded ? "▲" : "▼"}
              </span>
            </button>

            {isExpanded && (
              <div className="ml-8 mr-2 mb-1 rounded-lg border border-border bg-bg/60 px-3 py-2">
                <pre className="overflow-x-auto text-[10px] leading-relaxed text-muted whitespace-pre-wrap break-all">
                  {JSON.stringify(step.output_data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
