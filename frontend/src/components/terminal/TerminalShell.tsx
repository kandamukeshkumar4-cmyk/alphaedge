"use client";

/**
 * Loop V79 (A5) — Research Terminal shell.
 * assistant-ui composer + session sidebar + streamed step cards + scoreboard.
 * Fetch lives in `@/lib/terminal-api` (swap via setTerminalFetch).
 */

import { useCallback, useEffect, useState } from "react";

import { TerminalBullBear } from "@/components/terminal/TerminalBullBear";
import { TerminalScoreboard } from "@/components/terminal/TerminalScoreboard";
import { TerminalComposer } from "@/components/terminal/TerminalComposer";
import { TerminalSessionSidebar } from "@/components/terminal/TerminalSessionSidebar";
import { TerminalStepCard } from "@/components/terminal/TerminalStepCard";
import { PageHeader } from "@/components/ui/kit";
import { cn } from "@/lib/cn";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";
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
  const [view, setView] = useState<"dashboard" | "canvas">("dashboard");
  const [apiSource, setApiSource] = useState<"live" | "mock">("mock");

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
    setComposerKey((k) => k + 1);
  }, []);

  return (
    <div className="mx-auto max-w-[1600px] px-3 py-4 sm:px-4 sm:py-6" data-testid="terminal-page">
      <PageHeader
        kicker="Paper research"
        title="Research Terminal"
        subtitle="Ask a question → plan → streamed steps with real tables and charts → confluence scoreboard. Simulated funds only."
        actions={
          <div
            role="tablist"
            aria-label="Session view"
            className="flex rounded-lg border border-border bg-surface p-0.5"
          >
            {(["dashboard", "canvas"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={view === tab}
                data-testid={`terminal-view-${tab}`}
                onClick={() => setView(tab)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-[11px] font-bold capitalize transition",
                  view === tab ? "bg-primary-dim text-primary" : "text-muted hover:text-text",
                )}
              >
                {tab}
              </button>
            ))}
          </div>
        }
      />

      <p
        className="mb-4 rounded-lg border border-primary/20 bg-primary-dim/40 px-3 py-2 text-xs text-primary"
        data-testid="terminal-paper-banner"
      >
        {PAPER_TRADING_DISCLAIMER}
        {apiSource === "mock" ? (
          <span className="ml-2 font-mono text-[10px] uppercase text-muted-2">
            · local mock
          </span>
        ) : null}
      </p>

      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        <div className="min-h-[280px] lg:min-h-[640px]">
          <TerminalSessionSidebar
            sessions={sessions}
            activeId={activeId}
            onSelect={(id) => void loadSession(id)}
            onNew={onNew}
            loading={listLoading}
          />
        </div>

        <div className="min-w-0 space-y-4">
          {view === "dashboard" ? (
            <div data-testid="terminal-dashboard" className="space-y-4">
              <TerminalComposer
                key={composerKey}
                senses={senses}
                onSensesChange={setSenses}
                onAsk={onAsk}
                isRunning={running}
              />

              {error ? (
                <p className="rounded-lg border border-danger/30 bg-danger-dim/40 px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              ) : null}

              {session ? (
                <div className="rounded-xl border border-border bg-surface px-4 py-3">
                  <p className="font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted-2">
                    Active session · {session.status}
                    {session.market_slug ? ` · ${session.market_slug}` : ""}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-text">{session.question}</p>
                </div>
              ) : null}

              <section
                aria-label="Research steps"
                className="space-y-3"
                data-testid="terminal-session-body"
              >
                <h2 className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-muted">
                  Steps {running ? "· streaming" : ""}
                </h2>
                {steps.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted">
                    {running
                      ? "Streaming research steps…"
                      : "Resume a session or ask a question to stream numbered step cards."}
                  </p>
                ) : (
                  steps.map((step) => <TerminalStepCard key={step.id} step={step} />)
                )}
              </section>

              <section aria-label="Confluence scoreboard" className="space-y-3">
                <h2 className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-muted">
                  Confluence scoreboard
                </h2>
                <TerminalScoreboard lenses={scoreboard} />
                <TerminalBullBear bullCase={bull} bearCase={bear} />
              </section>
            </div>
          ) : (
            <div
              data-testid="terminal-canvas-placeholder"
              className="rounded-xl border border-dashed border-border bg-surface/40 px-4 py-12 text-center"
            >
              <p className="text-sm font-semibold text-text">Canvas view</p>
              <p className="mt-1 text-xs text-muted">
                Node graph arrives in ticket A6. Dashboard stays available meanwhile.
              </p>
              {session ? (
                <p className="mt-3 font-mono text-[11px] text-muted-2">
                  Session {session.id} · {steps.length} steps
                </p>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
