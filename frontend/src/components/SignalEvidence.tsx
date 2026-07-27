// F04: shared evidence renderer for signal surfaces (/signals + /feed).
// news:mispricing → headline + source link + model-vs-market edge.
// anomaly:unusual_flow → neutral "no public catalyst found" note.
import type { SignalEvidence } from "@/lib/signal-evidence";

export function SignalEvidenceBlock({ evidence }: { evidence: SignalEvidence }) {
  if (evidence.kind === "news") {
    return (
      <div className="mt-3 rounded-lg border border-accent/25 bg-accent/8 px-3 py-2.5">
        <p className="text-[10px] font-black uppercase tracking-[0.08em] text-accent">Evidence</p>
        <p className="mt-1 text-sm font-semibold text-text">{evidence.headline}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
          {evidence.modelP !== null ? (
            <span className="font-mono">forecast {(evidence.modelP * 100).toFixed(0)}%</span>
          ) : null}
          {evidence.marketP !== null ? (
            <span className="font-mono">market {(evidence.marketP * 100).toFixed(0)}%</span>
          ) : null}
          {evidence.edgeLabel ? (
            <span className="font-mono font-bold text-accent">edge {evidence.edgeLabel}</span>
          ) : null}
          {evidence.url ? (
            <a
              href={evidence.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-accent hover:underline"
            >
              Source ↗
            </a>
          ) : null}
        </div>
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-lg border border-border bg-surface-2 px-3 py-2.5">
      <p className="text-[10px] font-black uppercase tracking-[0.08em] text-muted-2">Catalyst</p>
      <p className="mt-1 text-xs text-muted">{evidence.note}</p>
    </div>
  );
}
