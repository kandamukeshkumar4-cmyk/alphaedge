import { pct, type Market } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

export function AIForecastPanel({ market }: { market: Market }) {
  const f = market.forecast;
  const edgeUp = f.edge >= 0;
  return (
    <div className="rounded-xl border border-primary/20 bg-primary-dim p-4">
      <div className="flex items-center gap-2">
        <span className="text-base">🤖</span>
        <h3 className="text-sm font-black text-text">AI forecast</h3>
        <span className="ml-auto rounded-md bg-bg/40 px-2 py-0.5 font-mono text-[11px] text-muted">
          XGBoost · updated 2h ago
        </span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <Metric label="Model" value={pct(f.prob)} tone="primary" />
        <Metric label="Confidence" value={pct(f.confidence)} />
        <Metric
          label="Edge"
          value={`${edgeUp ? "+" : ""}${Math.round(f.edge * 100)}%`}
          tone={edgeUp ? "primary" : "danger"}
        />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-text">{f.reasoning}</p>

      <div className="mt-3 flex items-center justify-between border-t border-primary/15 pt-3 text-xs text-muted">
        <span>Calibration (Brier)</span>
        <span className="font-mono font-bold text-text">{f.brier.toFixed(4)}</span>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "primary" | "danger";
}) {
  return (
    <div className="rounded-lg border border-border bg-bg/40 p-2">
      <div className="text-[11px] text-muted">{label}</div>
      <div
        className={cn(
          "mt-0.5 font-mono text-lg font-black",
          tone === "primary" && "text-primary",
          tone === "danger" && "text-danger",
          !tone && "text-text",
        )}
      >
        {value}
      </div>
    </div>
  );
}
