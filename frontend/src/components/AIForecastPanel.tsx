import { pct, type Market } from "@/lib/mock-data";
import { cn } from "@/lib/cn";

/** Format a stdev on the 0–1 probability scale as ± percentage points. */
function fmtStdevPts(stdev: number): string {
  return `±${(stdev * 100).toFixed(1)}pt`;
}

export function AIForecastPanel({ market, demo = false }: { market: Market; demo?: boolean }) {
  const f = market.forecast;
  const edgeUp = f.edge >= 0;
  // loop6 — ensemble surface. Only meaningful when >1 model contributed; a
  // single-model / older backend leaves nModels undefined → renders nothing.
  const isEnsemble = typeof f.nModels === "number" && f.nModels > 1;
  const perModel = f.perModel ?? [];
  const toolsUsed = f.toolsUsed ?? [];
  return (
    <div className="rounded-2xl border border-accent/30 bg-accent-dim p-4 shadow-glow">
      {demo ? (
        <p className="mb-3 text-center text-xs text-muted-2">
          Showing demo forecast. Model probability and edge are sample data, not live.
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-lg bg-gradient-to-br from-accent to-[#0D9488] font-mono text-[11px] font-black text-bg">
          AI
        </span>
        <h3 className="text-sm font-black text-text">AI forecast</h3>
        <span className="ml-auto rounded-full border border-accent/30 bg-bg/40 px-2.5 py-0.5 font-mono text-[11px] text-accent">
          XGBoost · 2h ago
        </span>
      </div>

      {isEnsemble ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-accent/30 bg-bg/40 px-2.5 py-0.5 font-mono text-[11px] text-accent">
            {f.nModels} models{typeof f.stdev === "number" ? ` · ${fmtStdevPts(f.stdev)}` : ""}
          </span>
          {f.spreadFlag ? (
            <span
              className="rounded-full border border-danger/40 bg-danger/10 px-2.5 py-0.5 font-mono text-[11px] font-bold text-danger"
              title="Models materially disagree (stdev > 0.15)"
            >
              ⚠ high spread
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <Metric label="Model" value={pct(f.prob)} tone="accent" />
        <Metric label="Confidence" value={pct(f.confidence)} />
        <Metric
          label="Edge"
          value={`${edgeUp ? "+" : ""}${Math.round(f.edge * 100)}%`}
          tone={edgeUp ? "primary" : "danger"}
        />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-text">{f.reasoning}</p>

      {toolsUsed.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wide text-muted">Tools</span>
          {toolsUsed.map((tool) => (
            <span
              key={tool}
              className="rounded-md border border-border bg-bg/40 px-2 py-0.5 font-mono text-[11px] text-muted"
            >
              {tool}
            </span>
          ))}
        </div>
      ) : null}

      {perModel.length > 0 ? (
        <details className="mt-3 border-t border-accent/15 pt-3">
          <summary className="cursor-pointer text-xs font-bold text-muted">
            Per-model rationales ({perModel.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {perModel.map((m, i) => (
              <li key={`${m.provider}-${i}`} className="rounded-lg border border-border bg-bg/30 p-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-mono font-bold text-text">{m.provider}</span>
                  <span className="font-mono text-accent">{pct(m.prob)}</span>
                </div>
                {m.rationale ? (
                  <p className="mt-1 text-xs leading-relaxed text-muted">{m.rationale}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <div className="mt-3 flex items-center justify-between border-t border-accent/15 pt-3 text-xs text-muted">
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
  tone?: "accent" | "primary" | "danger";
}) {
  return (
    <div className="rounded-xl border border-border bg-bg/40 p-2">
      <div className="text-[11px] text-muted">{label}</div>
      <div
        className={cn(
          "mt-0.5 font-mono text-lg font-black",
          tone === "accent" && "text-accent",
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
