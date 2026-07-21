"use client";

export function TerminalBullBear({
  bullCase,
  bearCase,
}: {
  bullCase?: string | null;
  bearCase?: string | null;
}) {
  if (!bullCase && !bearCase) return null;

  return (
    <section
      aria-label="Bull and bear cases"
      data-testid="terminal-bull-bear"
      className="grid gap-3 sm:grid-cols-2"
    >
      <div className="rounded-xl border border-primary/25 bg-primary-dim/20 p-4">
        <h3 className="text-[11px] font-black uppercase tracking-[0.12em] text-primary">
          Bull case
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-text">
          {bullCase?.trim() || "No bull case yet."}
        </p>
        <p className="mt-2 text-[10px] text-muted-2">Paper research only — simulated funds.</p>
      </div>
      <div className="rounded-xl border border-danger/25 bg-danger/5 p-4">
        <h3 className="text-[11px] font-black uppercase tracking-[0.12em] text-danger">
          Bear case
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-text">
          {bearCase?.trim() || "No bear case yet."}
        </p>
        <p className="mt-2 text-[10px] text-muted-2">Paper research only — no execution.</p>
      </div>
    </section>
  );
}
