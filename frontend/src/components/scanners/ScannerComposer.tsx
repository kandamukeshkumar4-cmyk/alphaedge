"use client";

import { useState } from "react";

import { cn } from "@/lib/cn";
import {
  compileScannerConversational,
  createScanner,
  scheduleLabel,
  stepLabel,
  testfireCompileDraft,
  type ClarifyQuestion,
  type CompileAnswer,
  type CompileScannerResult,
  type Scanner,
  type ScannerCompiler,
  type TestfireResult,
} from "@/lib/scanners-api";

/*
 * Loop V84 (U2) — "Describe a scanner" hero.
 * Loop V88 (V2) — compile badge + warnings.
 * Loop 116 — conversational clarify → testfire → publish dialogue.
 * Research-only: a scanner spec is a read plan, never an order path.
 */

const SEED_PROMPTS = [
  "NBA whale flow + price trend every 15 minutes, volume above 50,000",
  "Daily election news sentiment digest with model edge",
  "Watch crypto whale flow, top 10 markets, every hour",
  "Alert me about big NBA movers soon",
];

type ChatTurn =
  | { role: "user"; text: string }
  | { role: "agent"; text: string; questions?: ClarifyQuestion[] };

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
  const [testfiring, setTestfiring] = useState(false);
  const [preview, setPreview] = useState<CompileScannerResult | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [pendingQuestions, setPendingQuestions] = useState<ClarifyQuestion[]>([]);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [testfire, setTestfire] = useState<TestfireResult | null>(null);

  const trimmed = text.trim();
  const clarifying = pendingQuestions.length > 0;
  const ready = preview?.status === "ready" && preview.spec.steps.length > 0;

  async function handleCompile() {
    if (!trimmed || compiling) return;
    setCompiling(true);
    setTestfire(null);
    try {
      const result = await compileScannerConversational({ prompt: trimmed }, token);
      setDraftId(result.draft_id);
      setPreview(result);
      setTurns([
        { role: "user", text: trimmed },
        {
          role: "agent",
          text:
            result.status === "needs_clarification"
              ? "I can draft most of this — a few details still need your call:"
              : "Spec looks complete. Review it, test-fire, then publish.",
          questions:
            result.status === "needs_clarification" ? result.questions : undefined,
        },
      ]);
      if (result.status === "needs_clarification") {
        setPendingQuestions(result.questions);
        setAnswerDrafts({});
      } else {
        setPendingQuestions([]);
      }
    } finally {
      setCompiling(false);
    }
  }

  async function submitAnswers(answers: CompileAnswer[]) {
    if (!draftId || compiling || answers.length === 0) return;
    setCompiling(true);
    setTestfire(null);
    try {
      const label = answers.map((a) => a.answer).join(" · ");
      const result = await compileScannerConversational(
        { prompt: "", draft_id: draftId, answers },
        token,
      );
      setDraftId(result.draft_id);
      setPreview(result);
      setTurns((prev) => [
        ...prev,
        { role: "user", text: label },
        {
          role: "agent",
          text:
            result.status === "needs_clarification"
              ? "Still a couple of open items:"
              : "Ready — review the spec, run a test fire, then publish.",
          questions:
            result.status === "needs_clarification" ? result.questions : undefined,
        },
      ]);
      if (result.status === "needs_clarification") {
        setPendingQuestions(result.questions);
        setAnswerDrafts({});
      } else {
        setPendingQuestions([]);
        setAnswerDrafts({});
      }
    } finally {
      setCompiling(false);
    }
  }

  async function handleSubmitAnswers() {
    const answers: CompileAnswer[] = pendingQuestions
      .map((q) => ({
        question_id: q.id,
        answer: (answerDrafts[q.id] || "").trim(),
      }))
      .filter((a) => a.answer.length > 0);
    await submitAnswers(answers);
  }

  async function handleTestfire() {
    if (!draftId || !ready || testfiring) return;
    setTestfiring(true);
    try {
      const result = await testfireCompileDraft(draftId, token);
      setTestfire(result);
    } finally {
      setTestfiring(false);
    }
  }

  async function handleCreate() {
    if (!preview || preview.status !== "ready" || creating) return;
    setCreating(true);
    try {
      const { scanner } = await createScanner(
        { name: preview.spec.name, spec: preview.spec },
        token,
      );
      onCreated(scanner);
      setPreview(null);
      setText("");
      setDraftId(null);
      setPendingQuestions([]);
      setTurns([]);
      setTestfire(null);
    } finally {
      setCreating(false);
    }
  }

  function resetAuthoring() {
    setPreview(null);
    setDraftId(null);
    setPendingQuestions([]);
    setAnswerDrafts({});
    setTurns([]);
    setTestfire(null);
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
          Scanner Studio · conversational authoring
        </p>
        <h2
          id="scanners-composer-title"
          className="mt-2 text-xl font-black tracking-tight text-text sm:text-2xl"
        >
          Describe a scanner
        </h2>
        <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted">
          Plain English in. When something is ambiguous — schedule, thresholds, universe —
          we ask. Then test-fire a dry run and publish. Alerts stay in-app only (nothing is
          emailed). Scanners only read markets; they never place orders.
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
            disabled={clarifying}
            placeholder="e.g. Scan NBA markets where whale flow and the 7-day price trend agree, every 15 minutes, volume above 50,000"
            className={cn(
              "w-full resize-none rounded-xl border border-border bg-bg/70 px-3.5 py-3 text-sm text-text placeholder:text-muted-2",
              "transition focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/20",
              "disabled:opacity-60",
            )}
          />
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            {SEED_PROMPTS.map((seed) => (
              <button
                key={seed}
                type="button"
                onClick={() => setText(seed)}
                disabled={clarifying}
                className="rounded-full border border-border bg-bg/50 px-2.5 py-1 text-[11px] font-semibold text-muted transition hover:border-primary/40 hover:text-primary disabled:opacity-40"
              >
                {seed}
              </button>
            ))}
            <button
              type="button"
              onClick={() => void handleCompile()}
              disabled={!trimmed || compiling || clarifying}
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
            {clarifying || ready ? (
              <button
                type="button"
                onClick={resetAuthoring}
                data-testid="scanners-authoring-reset"
                className="inline-flex h-9 items-center rounded-lg border border-border px-3.5 text-[13px] font-semibold text-muted transition hover:border-border-light hover:text-text"
              >
                Start over
              </button>
            ) : null}
          </div>
        </div>

        {/* Chat transcript */}
        {turns.length > 0 ? (
          <div
            data-testid="scanners-authoring-chat"
            className="mt-5 space-y-2.5"
            aria-live="polite"
          >
            {turns.map((turn, i) => (
              <div
                key={`${turn.role}-${i}`}
                data-testid={
                  turn.role === "user" ? "scanners-chat-user" : "scanners-chat-agent"
                }
                className={cn(
                  "rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed",
                  turn.role === "user"
                    ? "ml-8 border border-primary/25 bg-primary/10 text-text"
                    : "mr-8 border border-border bg-bg/60 text-muted",
                )}
              >
                <p className="font-mono text-[9px] font-black uppercase tracking-[0.14em] text-muted-2">
                  {turn.role === "user" ? "You" : "Compiler"}
                </p>
                <p className="mt-1 text-text">{turn.text}</p>
              </div>
            ))}
          </div>
        ) : null}

        {/* Clarifying questions */}
        {clarifying ? (
          <div
            data-testid="scanners-clarify"
            className="t-card-open mt-4 space-y-4 rounded-xl border border-secondary/30 bg-bg/60 p-4 sm:p-5"
          >
            <p className="font-mono text-[10px] font-black uppercase tracking-[0.16em] text-secondary">
              Clarifying · round answers
            </p>
            {pendingQuestions.map((q) => (
              <div
                key={q.id}
                data-testid="scanners-clarify-question"
                data-kind={q.kind}
                className="space-y-2"
              >
                <p className="text-[13px] font-semibold text-text">{q.question}</p>
                <div className="flex flex-wrap gap-1.5">
                  {q.suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      data-testid="scanners-clarify-suggestion"
                      onClick={() =>
                        setAnswerDrafts((prev) => ({ ...prev, [q.id]: s }))
                      }
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-[11px] font-semibold transition",
                        answerDrafts[q.id] === s
                          ? "border-primary/50 bg-primary/15 text-primary"
                          : "border-border bg-bg/50 text-muted hover:border-primary/40 hover:text-primary",
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                <input
                  data-testid="scanners-clarify-input"
                  value={answerDrafts[q.id] ?? ""}
                  onChange={(e) =>
                    setAnswerDrafts((prev) => ({ ...prev, [q.id]: e.target.value }))
                  }
                  placeholder="Or type your answer…"
                  className="w-full rounded-lg border border-border bg-bg/70 px-3 py-2 text-[13px] text-text placeholder:text-muted-2 focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
            ))}
            <button
              type="button"
              data-testid="scanners-clarify-submit"
              onClick={() => void handleSubmitAnswers()}
              disabled={
                compiling ||
                pendingQuestions.every((q) => !(answerDrafts[q.id] || "").trim())
              }
              className={cn(
                "inline-flex h-9 items-center gap-2 rounded-lg bg-secondary px-4 text-[13px] font-bold text-bg transition hover:brightness-110 active:scale-95",
                "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
              )}
            >
              {compiling ? "Updating…" : "Send answers"}
            </button>
          </div>
        ) : null}

        {/* Ready preview + testfire + publish */}
        {preview && preview.status === "ready" ? (
          <div
            data-testid="scanners-preview"
            className="t-card-open mt-5 rounded-xl border border-primary/30 bg-bg/60 p-4 sm:p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-mono text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                Spec ready · {preview.source === "live" ? "live" : "local"} compile
              </p>
              <div className="flex items-center gap-1.5">
                <CompilerBadge compiler={preview.compiler} />
                <span className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">
                  draft {draftId ? draftId.slice(0, 8) : "—"}
                </span>
              </div>
            </div>

            <h3 className="mt-2.5 text-[15px] font-black tracking-tight text-text">
              {preview.spec.name}
            </h3>

            <div className="mt-3 grid gap-4 sm:grid-cols-[1fr_auto]">
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
                  <dt className="text-muted-2">delivery</dt>
                  <dd className="font-bold text-text">in-app only</dd>
                </div>
              </dl>
            </div>

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

            {testfire ? (
              <div
                data-testid="scanners-testfire-result"
                className="mt-4 rounded-xl border border-gold/35 bg-gold/5 p-3.5"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-gold/45 bg-gold/15 px-2 py-0.5 font-mono text-[10px] font-black uppercase tracking-[0.14em] text-gold">
                    Test fire · dry run
                  </span>
                  <span className="font-mono text-[11px] text-muted-2">
                    {testfire.summary.status}
                    {testfire.summary.is_test ? " · is_test" : ""}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em]">
                  <span className="rounded border border-border bg-bg/60 px-2 py-1 text-muted">
                    universe {testfire.summary.counts.universe}
                  </span>
                  <span className="rounded border border-border bg-bg/60 px-2 py-1 text-muted">
                    candidates {testfire.summary.counts.candidates}
                  </span>
                  <span className="rounded border border-gold/30 bg-gold/10 px-2 py-1 text-gold">
                    aligned {testfire.summary.counts.aligned}
                  </span>
                </div>
                <ul
                  data-testid="scanners-testfire-matches"
                  className="mt-3 space-y-1.5"
                >
                  {testfire.top_matches.length === 0 ? (
                    <li className="text-[12px] text-muted">No matches in this dry run.</li>
                  ) : (
                    testfire.top_matches.map((m) => (
                      <li
                        key={m.market_slug}
                        className="flex items-center justify-between gap-2 rounded-lg border border-border/60 bg-bg/50 px-2.5 py-1.5"
                      >
                        <span className="truncate text-[12.5px] font-bold text-text">
                          {m.title}
                        </span>
                        <span className="shrink-0 font-mono text-[9.5px] text-muted-2">
                          {m.aligned ? "aligned" : "—"}
                        </span>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => void handleTestfire()}
                disabled={testfiring || !draftId}
                data-testid="scanners-testfire"
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-lg border border-gold/45 bg-gold/10 px-4 text-[13px] font-bold text-gold transition hover:bg-gold/15 active:scale-95",
                  "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
                )}
              >
                {testfiring ? "Test firing…" : "Test fire"}
              </button>
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
                    Publishing…
                  </>
                ) : (
                  <>Publish</>
                )}
              </button>
              <button
                type="button"
                onClick={resetAuthoring}
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
