"use client";

import { useState } from "react";

import { cn } from "@/lib/cn";
import {
  compileScanner,
  createScanner,
  scheduleLabel,
  stepLabel,
  type CompileScannerResult,
  type Scanner,
  type ScannerCompiler,
} from "@/lib/scanners-api";

/*
 * Loop V84 (U2) — "Describe a scanner" hero. Plain English → POST compile →
 * spec PREVIEW panel (universe, schedule, numbered step chips) → Create →
 * POST create → the new card lands at the top of the grid. Research-only:
 * a scanner spec is a read plan, never an order path.
 *
 * Loop V88 (V2) — compile feedback: the preview carries the compiler badge
 * ("Compiled: deterministic" mint / "Compiled: AI-assisted" blue) and the
 * backend's deterministic warnings[] as amber notice lines above Create.
 */

const SEED_PROMPTS = [
  "NBA whale flow + price trend every 15 minutes, volume above 50,000",
  "Daily election news sentiment digest with model edge",
  "Watch crypto whale flow, top 10 markets, every hour",
];

// Loop V88 (V2) — compiler provenance badge. Mint for the deterministic
// keyword parser, blue when the LLM planner assisted. Never red.
function compilerBadgeClasses(compiler: ScannerCompiler): string {
  return compiler === "deterministic"
    ? "border-primary/40 bg-primary/10 text-primary"
    : "border-secondary/40 bg-secondary/10 text-secondary";
}

function CompilerBadge({ compiler }: { compiler: ScannerCompiler }) {
  return (
    <span
      data-testid="scanners-compiler-badge"
      data-compiler={compiler}
      title={
        compiler === "deterministic"
          ? "Compiled by the deterministic keyword parser"
          : "Compiled with AI assistance"
      }
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5",
        "font-mono text-[10px] font-bold tracking-[0.08em]",
        compilerBadgeClasses(compiler),
      )}
    >
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          compiler === "deterministic" ? "bg-primary" : "bg-secondary",
        )}
      />
      Compiled: {compiler === "deterministic" ? "deterministic" : "AI-assisted"}
    </span>
  );
}

function SpecChip({ index, label }: { index: number; label: string }) {
  return (
    <li
      className={cn(
        "t-card-open flex items-center gap-2 rounded-lg border border-border bg-bg/60 px-2.5 py-1.5",
        index > 0 ? `t-stagger-${Math.min(index, 4)}` : "",
      )}
    >
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/15 font-mono text-[10px] font-black text-primary">
        {String(index + 1).padStart(2, "0")}
      </span>
      <span className="font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-text">
        {label}
      </span>
    </li>
  );
}

export function ScannerComposer({
  token,
  onCreated,
}: {
  token: string | null;
  onCreated: (scanner: Scanner) => void;
}) {
  const [text, setText] = useState("");
  const [compiling, setCompiling] = useState(false);
  const [creating, setCreating] = useState(false);
  const [preview, setPreview] = useState<CompileScannerResult | null>(null);

  const trimmed = text.trim();

  async function handleCompile() {
    if (!trimmed || compiling) return;
    setCompiling(true);
    try {
      const result = await compileScanner(trimmed, token);
      setPreview(result);
    } finally {
      setCompiling(false);
    }
  }

  async function handleCreate() {
    if (!preview || creating) return;
    setCreating(true);
    try {
      const { scanner } = await createScanner(
        { name: preview.spec.name, spec: preview.spec },
        token,
      );
      onCreated(scanner);
      setPreview(null);
      setText("");
    } finally {
      setCreating(false);
    }
  }

  return (
    <section
      data-testid="scanners-composer"
      aria-labelledby="scanners-composer-title"
      className="relative overflow-hidden rounded-2xl border border-border bg-surface"
      style={{
        backgroundImage:
          "radial-gradient(80% 130% at 10% 0%, rgba(0,232,176,0.10) 0%, transparent 55%), radial-gradient(70% 120% at 100% 100%, rgba(75,158,255,0.06) 0%, transparent 60%)",
      }}
    >
      <div className="px-5 py-6 sm:px-7">
        <p className="flex items-center gap-2 font-mono text-[10px] font-black uppercase tracking-[0.16em] text-primary">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_10px_rgba(45,212,191,0.8)]" />
          Scanner Studio · NL → spec compiler
        </p>
        <h2
          id="scanners-composer-title"
          className="mt-2 text-xl font-black tracking-tight text-text sm:text-2xl"
        >
          Describe a scanner
        </h2>
        <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted">
          Plain English in, a structured alert spec out — universe, schedule and an ordered step
          pipeline. Review the compiled preview, then create it. Scanners only read markets; they
          never place orders.
        </p>

        <div className="mt-4">
          <label htmlFor="scanner-request" className="sr-only">
            Describe the scanner you want
          </label>
          <textarea
            id="scanner-request"
            data-testid="scanners-request-input"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter") void handleCompile();
            }}
            placeholder="e.g. Scan NBA markets where whale flow and the 7-day price trend agree, every 15 minutes, volume above 50,000"
            className={cn(
              "w-full resize-none rounded-xl border border-border bg-bg/70 px-3.5 py-3 text-sm text-text placeholder:text-muted-2",
              "transition focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/20",
            )}
          />
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            {SEED_PROMPTS.map((seed) => (
              <button
                key={seed}
                type="button"
                onClick={() => setText(seed)}
                className="rounded-full border border-border bg-bg/50 px-2.5 py-1 text-[11px] font-semibold text-muted transition hover:border-primary/40 hover:text-primary"
              >
                {seed}
              </button>
            ))}
            <button
              type="button"
              onClick={() => void handleCompile()}
              disabled={!trimmed || compiling}
              data-testid="scanners-compile"
              className={cn(
                "ml-auto inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-[13px] font-bold text-bg shadow-glow transition hover:brightness-110 active:scale-95",
                "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
              )}
            >
              {compiling ? (
                <>
                  <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-bg" />
                  Compiling…
                </>
              ) : (
                <>Compile ↵</>
              )}
            </button>
          </div>
        </div>

        {preview ? (
          <div
            data-testid="scanners-preview"
            className="t-card-open mt-5 rounded-xl border border-primary/30 bg-bg/60 p-4 sm:p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                Spec preview · compiled {preview.source === "live" ? "live" : "locally"}
              </p>
              <div className="flex items-center gap-1.5">
                <CompilerBadge compiler={preview.compiler} />
                <span className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
                  nothing is saved yet
                </span>
              </div>
            </div>

            <h3 className="mt-2.5 text-[15px] font-black tracking-tight text-text">
              {preview.spec.name}
            </h3>

            <div className="mt-3 grid gap-4 sm:grid-cols-[1fr_auto]">
              {/* Step pipeline — numbered chips, compiler order. */}
              <div>
                <p className="mb-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-muted-2">
                  Steps · {preview.spec.steps.length}
                </p>
                {preview.spec.steps.length > 0 ? (
                  <ol
                    data-testid="scanners-preview-steps"
                    className="flex flex-wrap gap-1.5"
                    aria-label="Compiled spec steps"
                  >
                    {preview.spec.steps.map((step, i) => (
                      <SpecChip key={`${step.type}-${i}`} index={i} label={stepLabel(step)} />
                    ))}
                  </ol>
                ) : (
                  <p className="text-[12px] text-muted">
                    No signal steps detected — mention whale flow, price trend, news sentiment or
                    model edge.
                  </p>
                )}
              </div>

              {/* Universe + schedule block. */}
              <dl className="min-w-[190px] space-y-1.5 rounded-lg border border-border bg-surface/70 px-3 py-2.5 font-mono text-[11px]">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-2">universe</dt>
                  <dd className="font-bold text-text">
                    {preview.spec.universe.categories.length > 0
                      ? preview.spec.universe.categories.join(" · ")
                      : "all markets"}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-2">min volume</dt>
                  <dd className="font-bold text-text">
                    {preview.spec.universe.minimum_volume > 0
                      ? `$${preview.spec.universe.minimum_volume.toLocaleString("en-US")}`
                      : "any"}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-2">schedule</dt>
                  <dd className="font-bold text-primary">{scheduleLabel(preview.spec)}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-2">top</dt>
                  <dd className="font-bold text-text">{preview.spec.limit} markets</dd>
                </div>
              </dl>
            </div>

            {preview.spec.notes.length > 0 ? (
              <p className="mt-2.5 text-[11px] text-muted-2">
                Unparsed fragments (ignored): {preview.spec.notes.join(", ")}
              </p>
            ) : null}

            {/* Loop V88 (V2) — deterministic compile warnings, amber, never
                blocking; rendered above the Create button. */}
            {preview.warnings.length > 0 ? (
              <ul
                data-testid="scanners-compile-warnings"
                aria-label="Compile warnings"
                className="mt-3 space-y-1 rounded-lg border border-gold/35 bg-gold/5 px-3 py-2"
              >
                {preview.warnings.map((warning) => (
                  <li
                    key={warning}
                    data-testid="scanners-compile-warning"
                    className="flex items-start gap-1.5 text-[11.5px] font-semibold leading-snug text-gold"
                  >
                    <span aria-hidden className="mt-px shrink-0">
                      ⚠
                    </span>
                    {warning}
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="mt-4 flex items-center gap-2">
              <button
                type="button"
                onClick={() => void handleCreate()}
                disabled={creating || preview.spec.steps.length === 0}
                data-testid="scanners-create"
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-[13px] font-bold text-bg shadow-glow transition hover:brightness-110 active:scale-95",
                  "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
                )}
              >
                {creating ? (
                  <>
                    <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-bg" />
                    Creating…
                  </>
                ) : (
                  <>Create scanner</>
                )}
              </button>
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="inline-flex h-9 items-center rounded-lg border border-border px-3.5 text-[13px] font-semibold text-muted transition hover:border-border-light hover:text-text"
              >
                Discard
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
