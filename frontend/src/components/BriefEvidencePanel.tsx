import type { AnalystBrief, EnsembleForecast, ToolUsage } from "@/lib/polyscout-api";
import { cn } from "@/lib/cn";

type BriefMarketContext = {
  model_prob?: number | null;
  market_implied?: number | null;
  edge?: number | null;
  ensemble?: EnsembleForecast | null;
};

export function BriefEvidencePanel({
  brief,
  context,
}: {
  brief: AnalystBrief;
  context?: BriefMarketContext | null;
}) {
  const metrics = deriveMetrics(brief, context);
  const ensemble = brief.ensemble ?? context?.ensemble ?? null;
  const tools = normalizeTools(brief.tools_used);
  const hasMetrics =
    metrics.modelProb !== null || metrics.marketProb !== null || metrics.edge !== null;
  const hasEnsemble = ensemble && typeof ensemble.n_models === "number";

  if (!hasMetrics && !hasEnsemble && tools.length === 0) return null;

  return (
    <section className="mt-8 rounded-2xl border border-border bg-surface p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
        Forecast vs market
      </h2>

      {hasMetrics ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <Metric label="Model" value={formatProb(metrics.modelProb)} tone="accent" />
          <Metric label="Market" value={formatProb(metrics.marketProb)} />
          <Metric
            label="Edge"
            value={formatSignedPct(metrics.edge)}
            tone={(metrics.edge ?? 0) >= 0 ? "primary" : "danger"}
          />
        </div>
      ) : null}

      {hasEnsemble ? (
        <div className="mt-4 rounded-xl border border-border bg-bg/40 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-accent/30 bg-accent-dim px-2.5 py-0.5 font-mono text-[11px] font-semibold text-accent">
              {ensemble.n_models} model{ensemble.n_models === 1 ? "" : "s"}
              {typeof ensemble.stdev === "number" ? ` · ${formatStdev(ensemble.stdev)}` : ""}
            </span>
            {ensemble.spread_flag ? (
              <span className="rounded-full border border-danger/40 bg-danger/10 px-2.5 py-0.5 font-mono text-[11px] font-bold text-danger">
                high spread
              </span>
            ) : null}
          </div>
          {ensemble.per_model && ensemble.per_model.length > 0 ? (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-semibold text-muted">
                Per-model rationales ({ensemble.per_model.length})
              </summary>
              <ul className="mt-2 space-y-2">
                {ensemble.per_model.map((member, index) => (
                  <li
                    key={`${member.provider}-${index}`}
                    className="rounded-lg border border-border bg-surface px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-3 text-[11px]">
                      <span className="font-mono font-semibold text-text">{member.provider}</span>
                      <span className="font-mono text-accent">{formatProb(member.prob)}</span>
                    </div>
                    {member.rationale ? (
                      <p className="mt-1 text-xs leading-relaxed text-muted">
                        {member.rationale}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}

      {tools.length > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] uppercase tracking-wide text-muted">Tools</span>
          {tools.map((tool) => (
            <span
              key={tool}
              className="rounded-md border border-border bg-bg/40 px-2 py-0.5 font-mono text-[11px] text-muted"
            >
              {tool}
            </span>
          ))}
        </div>
      ) : null}
    </section>
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
    <div className="rounded-xl border border-border bg-bg/40 p-3">
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

function deriveMetrics(brief: AnalystBrief, context?: BriefMarketContext | null) {
  const fromCitation = parseModelCitation(brief);
  const modelProb = firstNumber(brief.model_prob, context?.model_prob, fromCitation.modelProb);
  const edge = firstNumber(brief.edge, context?.edge, fromCitation.edge);
  const marketProb = firstNumber(
    brief.market_implied,
    context?.market_implied,
    modelProb !== null && edge !== null ? modelProb - edge : null,
  );

  return { modelProb, marketProb, edge };
}

function parseModelCitation(brief: AnalystBrief): {
  modelProb: number | null;
  edge: number | null;
} {
  for (const citation of brief.citations ?? []) {
    const ref = typeof citation.ref === "string" ? citation.ref : "";
    const match = ref.match(/model\s+p=([+-]?\d+(?:\.\d+)?)\s+edge=([+-]?\d+(?:\.\d+)?)/i);
    if (match) {
      return {
        modelProb: Number(match[1]),
        edge: Number(match[2]),
      };
    }
  }
  return { modelProb: null, edge: null };
}

function firstNumber(...values: Array<number | null | undefined>): number | null {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function formatProb(value: number | null): string {
  return value === null ? "n/a" : `${(value * 100).toFixed(1)}%`;
}

function formatSignedPct(value: number | null): string {
  if (value === null) return "n/a";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function formatStdev(value: number): string {
  return `±${(value * 100).toFixed(1)}pt`;
}

function normalizeTools(tools: AnalystBrief["tools_used"]): string[] {
  if (!Array.isArray(tools)) return [];
  return tools
    .map((tool) => {
      if (typeof tool === "string") return tool;
      if (!tool || typeof tool !== "object") return null;
      return toolLabel(tool);
    })
    .filter((tool): tool is string => Boolean(tool));
}

function toolLabel(tool: ToolUsage): string {
  const name = tool.tool;
  if (typeof tool.spread === "number") return `${name} spread ${tool.spread.toFixed(3)}`;
  if (typeof tool.points === "number") return `${name} ${tool.points} pts`;
  if (typeof tool.whale_count === "number") return `${name} ${tool.whale_count} whales`;
  if (tool.error) return `${name} error`;
  return name;
}
