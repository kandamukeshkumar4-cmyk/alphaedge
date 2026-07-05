"use client";

import { cn } from "@/lib/cn";

const NODE_META: Record<string, { label: string; description: string; icon: string }> = {
  data: { label: "Data", description: "Load market features and implied price.", icon: "📊" },
  news: { label: "News", description: "Enrich with last30days news sentiment.", icon: "📰" },
  prediction: { label: "Prediction", description: "Run XGBoost/LightGBM model forecast.", icon: "🔮" },
  risk: { label: "Risk", description: "Validate via RiskService → OrderIntent (paper only).", icon: "🛡️" },
  reasoning: { label: "Reasoning", description: "Compose a natural-language rationale.", icon: "💡" },
  execute: { label: "Execute", description: "Paper-execution gate (blocked unless risk approved).", icon: "⚡" },
};

interface NodeToggleCardProps {
  nodeName: string;
  selected: boolean;
  onToggle: (name: string) => void;
  disabled?: boolean;
}

export function NodeToggleCard({ nodeName, selected, onToggle, disabled = false }: NodeToggleCardProps) {
  const meta = NODE_META[nodeName] ?? {
    label: nodeName,
    description: "Agent graph node.",
    icon: "🔧",
  };

  return (
    <button
      type="button"
      onClick={() => !disabled && onToggle(nodeName)}
      disabled={disabled}
      aria-pressed={selected}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border p-4 text-left transition",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent",
        selected
          ? "border-accent bg-accent/10 shadow-sm"
          : "border-border bg-surface hover:border-accent/50 hover:bg-surface-2",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <span className="mt-0.5 text-2xl">{meta.icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text">{meta.label}</span>
          {selected && (
            <span className="rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-bold text-bg">
              ON
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted">{meta.description}</p>
      </div>
    </button>
  );
}
