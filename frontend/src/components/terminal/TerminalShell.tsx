"use client";

/**
 * Loop V79 — Research Terminal shell.
 * A8 polish: Xynth layout per goals/loop-v79/UI-DIRECTION.md —
 * 240px collapsible sidebar, ~880px centered main column (session title row
 * → step stream → sticky composer), segmented Dashboard|Description|Canvas
 * tabs with a 200ms sliding thumb, and an empty state with template cards.
 * Fetch lives in `@/lib/terminal-api` (swap via setTerminalFetch).
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { TerminalBullBear } from "@/components/terminal/TerminalBullBear";
import { TerminalScoreboard } from "@/components/terminal/TerminalScoreboard";
import { TerminalComposer } from "@/components/terminal/TerminalComposer";
import { TerminalSessionSidebar } from "@/components/terminal/TerminalSessionSidebar";
import { TerminalStepCard } from "@/components/terminal/TerminalStepCard";
import { EMPTY_STATE_TEMPLATES } from "@/components/terminal/terminal-templates";
import { cn } from "@/lib/cn";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";
import { useCountUp } from "@/lib/use-count-up";
import {
  createSession,
  getSession,
  listSessions,
  streamSession,
  toSessionSummary,
  type ResearchSession,
  type ResearchStep,
  type ScoreboardLens,
  type SenseId,
  type SessionSummary,
  TERMINAL_CANONICAL_MARKET,
} from "@/lib/terminal-api";

/** A6 — React Flow canvas is client-only (no SSR). */
const TerminalCanvas = dynamic(
  () => import("@/components/terminal/TerminalCanvas").then((m) => m.TerminalCanvas),
  {
    ssr: false,
    loading: () => (
      <div className="grid h-[520px] w-full place-items-center rounded-xl border border-border bg-bg/60 text-sm text-muted">
        Loading canvas…
      </div>
    ),
  },
);

type View = "dashboard" | "description" | "canvas";
const VIEWS: View[] = ["dashboard", "description", "canvas"];

function MenuIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function TerminalShell() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [steps, setSteps] = useState<ResearchStep[]>([]);
  const [scoreboard, setScoreboard] = useState<ScoreboardLens[]>([]);
  const [bull, setBull] = useState<string | null>(null);
  const [bear, setBear] = useState<string | null>(null);
  const [senses, setSenses] = useState<SenseId[]>([
    "odds",
    "whale",
    "news",
    "sentiment",
    "model",
    "arb",
  ]);
  const [running, setRunning] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [composerKey, setComposerKey] = useState(0);
  const [view, setView] = useState<View>("dashboard");
  const [apiSource, setApiSource] = useState<"live" | "mock">("mock");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileNav, setMobileNav] = useState(false);
  const [hideSteps, setHideSteps] = useState(false);

  const refreshList = useCallback(async () => {
    setListLoading(true);
    try {
      const { sessions: items, source } = await listSessions();
      setApiSource(source);
      setSessions(items.map(toSessionSummary));
    } finally {
      setListLoading(false);
    }
  }, []);

  const applySession = useCallback((s: ResearchSession) => {
    setActiveId(s.id);
    setSession(s);
    setSteps([...s.steps].sort((a, b) => a.sequence - b.sequence));
    setScoreboard(s.summary.scoreboard);
    setBull(s.summary.bull_case);
    setBear(s.summary.bear_case);
  }, []);

  const runStream = useCallback(
    async (id: string) => {
      setRunning(true);
      setError(null);
      setSteps([]);
      setScoreboard([]);
      setBull(null);
      setBear(null);
      try {
        for await (const ev of streamSession(id)) {
          if (ev.type === "step") {
            setSteps((prev) => {
              if (prev.some((s) => s.id === ev.step.id)) return prev;
              return [...prev, ev.step].sort((a, b) => a.sequence - b.sequence);
            });
          } else if (ev.type === "scoreboard") {
            setScoreboard(ev.scoreboard);
            setBull(ev.bull_case ?? null);
            setBear(ev.bear_case ?? null);
          } else if (ev.type === "done") {
            applySession(ev.session);
          } else if (ev.type === "error") {
            setError(ev.message);
          }
        }
        await refreshList();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Stream failed");
      } finally {
        setRunning(false);
      }
    },
    [applySession, refreshList],
  );

  const loadSession = useCallback(
    async (id: string) => {
      setError(null);
      setMobileNav(false);
      const { session: s, source } = await getSession(id);
      setApiSource(source);
      if (!s) {
        setError("Session not found.");
        return;
      }
      applySession(s);
      setView("dashboard");
      if (s.status === "draft" || s.status === "running") {
        await runStream(s.id);
      }
    },
    [applySession, runStream],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await refreshList();
      if (cancelled) return;
      const { sessions: items } = await listSessions();
      if (cancelled) return;
      if (items[0]) await loadSession(items[0].id);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshList, loadSession]);

  const onAsk = useCallback(
    async (question: string, selected: SenseId[]) => {
      setView("dashboard");
      const { session: created, source } = await createSession({
        question,
        market_slug: TERMINAL_CANONICAL_MARKET,
        senses: selected,
      });
      setApiSource(source);
      applySession(created);
      await runStream(created.id);
    },
    [applySession, runStream],
  );

  const onNew = useCallback(() => {
    setActiveId(null);
    setSession(null);
    setSteps([]);
    setScoreboard([]);
    setBull(null);
    setBear(null);
    setError(null);
    setView("dashboard");
    setMobileNav(false);
    setComposerKey((k) => k + 1);
  }, []);

  /** Canvas node click → back to Dashboard with that step in view. */
  const onSelectStep = useCallback((stepId: string) => {
    setView("dashboard");
    window.setTimeout(() => {
      document
        .getElementById(`terminal-step-${stepId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);
  }, []);

  const sidebar = (
    <TerminalSessionSidebar
      sessions={sessions}
      activeId={activeId}
      onSelect={(id) => void loadSession(id)}
      onNew={onNew}
      onTemplate={(q) => {
        setMobileNav(false);
        void onAsk(q, senses);
      }}
      loading={listLoading}
      onCollapse={() => {
        setSidebarOpen(false);
        setMobileNav(false);
      }}
    />
  );

  const viewIndex = VIEWS.indexOf(view);
  const stepCount = useCountUp(steps.length);
  const lensCount = useCountUp(scoreboard.length);

  return (
    <div className="mx-auto max-w-[1600px] px-3 py-4 sm:px-4 sm:py-6" data-testid="terminal-page">
      <div className="flex items-start gap-4">
        {/* Desktop sidebar (240px, collapsible) */}
        {sidebarOpen ? (
          <div className="hidden w-[240px] shrink-0 lg:block">
            <div className="sticky top-4 h-[calc(100dvh-7rem)] min-h-[480px]">{sidebar}</div>
          </div>
        ) : null}

        {/* Mobile sidebar sheet (<=768px quality bar) */}
        {mobileNav ? (
          <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setMobileNav(false)}
              className="absolute inset-0 bg-bg/70"
            />
            <div className="absolute inset-y-0 left-0 w-[280px] max-w-[85vw] p-2">{sidebar}</div>
          </div>
        ) : null}

        {/* Main column (~880px, centered) */}
        <div className="min-w-0 flex-1">
          <div className="mx-auto w-full max-w-[880px]">
            {/* Session title row: icon + name + LIVE/timestamp ··· tabs */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  if (window.matchMedia("(min-width: 1024px)").matches) {
                    setSidebarOpen(true);
                  } else {
                    setMobileNav(true);
                  }
                }}
                aria-label="Show sidebar"
                className={cn(
                  "rounded-lg border border-border bg-surface p-2 text-muted transition",
                  "hover:text-text focus-visible:outline-none active:scale-95",
                  sidebarOpen ? "lg:hidden" : "",
                )}
              >
                <MenuIcon />
              </button>
              <span
                aria-hidden="true"
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full",
                  running ? "bg-primary animate-pulse" : "bg-muted-2",
                )}
              />
              <p className="min-w-0 flex-1 truncate text-sm font-bold text-text">
                {session ? session.question : "New research"}
                <span
                  className={cn(
                    "ml-1 font-mono text-[10px] font-semibold uppercase tracking-wide",
                    running ? "text-primary" : "text-muted-2",
                  )}
                >
                  {running
                    ? "· LIVE"
                    : session
                      ? `· ${session.status} ${formatTimestamp(session.updated_at)}`
                      : "· draft"}
                </span>
              </p>
              <div
                role="tablist"
                aria-label="Session view"
                className="no-scrollbar relative flex shrink-0 overflow-x-auto rounded-lg border border-border bg-surface p-0.5"
              >
                {/* 200ms sliding thumb */}
                <span
                  aria-hidden="true"
                  className="absolute bottom-0.5 top-0.5 rounded-md bg-primary-dim transition-transform duration-200 ease-swift"
                  style={{
                    width: `calc((100% - 4px) / ${VIEWS.length})`,
                    left: "2px",
                    transform: `translateX(${viewIndex * 100}%)`,
                  }}
                />
                {VIEWS.map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    role="tab"
                    aria-selected={view === tab}
                    data-testid={`terminal-view-${tab}`}
                    onClick={() => setView(tab)}
                    className={cn(
                      "relative z-10 flex-1 whitespace-nowrap rounded-md px-3 py-1.5 text-[11px] font-bold capitalize transition-colors",
                      "focus-visible:outline-none active:scale-[0.98]",
                      view === tab ? "text-primary" : "text-muted hover:text-text",
                    )}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <p
              className="mt-3 rounded-lg border border-primary/20 bg-primary-dim/40 px-3 py-2 text-xs text-primary"
              data-testid="terminal-paper-banner"
            >
              {PAPER_TRADING_DISCLAIMER}
              {apiSource === "mock" ? (
                <span className="ml-2 font-mono text-[10px] uppercase text-muted-2">
                  · local mock
                </span>
              ) : null}
            </p>

            {view === "canvas" ? (
              <div className="mt-4">
                <TerminalCanvas
                  steps={steps}
                  scoreboard={scoreboard}
                  verdict={session?.summary.verdict ?? null}
                  running={running}
                  onSelectStep={onSelectStep}
                />
              </div>
            ) : view === "description" ? (
              <section
                aria-label="Session description"
                className="mt-4 space-y-3 rounded-xl border border-border bg-surface p-4"
              >
                <h2 className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-muted">
                  Description
                </h2>
                <p className="text-sm font-semibold text-text">
                  {session?.question ?? "No session yet — ask a question from the Dashboard tab."}
                </p>
                <dl className="grid gap-2 text-xs text-muted sm:grid-cols-2">
                  <div>
                    <dt className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
                      Market
                    </dt>
                    <dd className="mt-0.5 font-mono text-text">
                      {session?.market_slug ?? TERMINAL_CANONICAL_MARKET}
                    </dd>
                  </div>
                  <div>
                    <dt className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
                      Status
                    </dt>
                    <dd className="mt-0.5 capitalize text-text">{session?.status ?? "draft"}</dd>
                  </div>
                  <div>
                    <dt className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
                      Data senses
                    </dt>
                    <dd className="mt-0.5 capitalize text-text">{senses.join(", ")}</dd>
                  </div>
                  <div>
                    <dt className="font-mono text-[10px] uppercase tracking-wide text-muted-2">
                      Steps
                    </dt>
                    <dd className="mt-0.5 text-text">{steps.length} streamed · paper only</dd>
                  </div>
                </dl>
              </section>
            ) : session ? (
              /* In-session: step stream → sticky composer */
              <div data-testid="terminal-dashboard" className="mt-4">
                {error ? (
                  <p className="mb-4 rounded-lg border border-danger/30 bg-danger-dim/40 px-3 py-2 text-sm text-danger">
                    {error}
                  </p>
                ) : null}

                <section
                  aria-label="Research steps"
                  className="space-y-3"
                  data-testid="terminal-session-body"
                >
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-muted">
                      Steps{" "}
                      {steps.length > 0 ? <span className="tabular-nums">· {stepCount}</span> : ""}{" "}
                      {running ? "· streaming" : ""}
                    </h2>
                    <button
                      type="button"
                      data-testid="terminal-hide-steps"
                      aria-pressed={hideSteps}
                      onClick={() => setHideSteps((v) => !v)}
                      className="rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide text-muted transition hover:bg-surface-2 hover:text-text focus-visible:outline-none active:scale-95"
                    >
                      {hideSteps ? "Show steps" : "Hide steps"}
                    </button>
                  </div>
                  {steps.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted">
                      {running
                        ? "Streaming research steps…"
                        : "Resume a session or ask a question to stream numbered step cards."}
                    </p>
                  ) : (
                    steps.map((step, i) => (
                      <TerminalStepCard
                        key={step.id}
                        step={step}
                        hideSteps={hideSteps}
                        active={running && i === steps.length - 1}
                        stagger={i < 5 ? i : undefined}
                      />
                    ))
                  )}
                  {/* Reserved height for the next streamed step — no CLS. */}
                  {running ? (
                    <div
                      aria-hidden="true"
                      className="t-skeleton h-[76px] w-full rounded-xl border border-border"
                    />
                  ) : null}
                </section>

                <section aria-label="Confluence scoreboard" className="mt-6 space-y-3">
                  <h2 className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-muted">
                    Confluence scoreboard{" "}
                    {scoreboard.length > 0 ? (
                      <span className="tabular-nums">· {lensCount} lenses</span>
                    ) : (
                      ""
                    )}
                  </h2>
                  {running && scoreboard.length === 0 ? (
                    /* Reserved height until the scoreboard event lands. */
                    <div
                      aria-hidden="true"
                      className="t-skeleton h-[190px] w-full rounded-xl border border-border"
                    />
                  ) : null}
                  <TerminalScoreboard lenses={scoreboard} verdict={session?.summary.verdict} />
                  <TerminalBullBear bullCase={bull} bearCase={bear} />
                </section>

                {/* Sticky composer at bottom of the stream */}
                <div className="sticky bottom-3 z-10 mt-6">
                  <TerminalComposer
                    key={composerKey}
                    senses={senses}
                    onSensesChange={setSenses}
                    onAsk={onAsk}
                    isRunning={running}
                  />
                </div>
              </div>
            ) : (
              /* Empty state (new chat): headline, subline, composer, templates */
              <section
                aria-label="New research"
                className="flex min-h-[62dvh] flex-col items-center justify-center py-10 text-center"
              >
                <h2 className="max-w-xl text-3xl font-black tracking-tight text-text sm:text-4xl">
                  Find the edge in <span className="text-primary">seconds</span>
                </h2>
                <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
                  Ask a question — the terminal plans the research, streams numbered steps with
                  real tables and charts, and scores confluence. Paper trading only.
                </p>
                <div className="mt-8 w-full">
                  <TerminalComposer
                    key={composerKey}
                    senses={senses}
                    onSensesChange={setSenses}
                    onAsk={onAsk}
                    isRunning={running}
                  />
                </div>
                <div className="mt-8 grid w-full gap-3 sm:grid-cols-3">
                  {EMPTY_STATE_TEMPLATES.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => void onAsk(t.question, senses)}
                      className={cn(
                        "rounded-xl border border-border bg-surface p-4 text-left transition",
                        "hover:border-primary/40 hover:bg-surface-2/50",
                        "focus-visible:outline-none active:scale-[0.99]",
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <span
                          aria-hidden="true"
                          className={cn("h-1.5 w-1.5 rounded-full", t.dot)}
                        />
                        <span className="text-[13px] font-bold text-text">{t.name}</span>
                      </span>
                      <span className="mt-1.5 block text-[12px] leading-relaxed text-muted">
                        {t.blurb}
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
