"use client";

/**
 * Loop V60 (U3) — decision-log terminal for the /pods command center.
 * Streams GET /api/v1/heartbeat/decisions on a 5s poll: newest decisions land
 * on top and genuinely new rows blink once with the existing trade-token
 * flashes (buy side = green flash, sell side = red flash, neutral rows slide
 * in). If the heartbeat endpoint 404s the terminal says so honestly — no
 * synthetic log rows, ever. Read-only telemetry; there is no order path here.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import {
  decisionActionTone,
  decisionKey,
  fetchHeartbeatDecisions,
  findNewDecisionKeys,
  formatDecisionTime,
  sortDecisionsNewestFirst,
  type DecisionActionTone,
  type HeartbeatDecision,
  type HeartbeatDecisionsResponse,
  type PodsApiResult,
} from "@/lib/pods-api";

const DEFAULT_POLL_MS = 5000;
const MAX_ROWS = 50;

type TerminalState =
  | { phase: "loading" }
  | { phase: "ready"; result: PodsApiResult<HeartbeatDecisionsResponse> };

export function DecisionLogTerminal({
  pollMs = DEFAULT_POLL_MS,
}: {
  pollMs?: number;
}) {
  const [state, setState] = useState<TerminalState>({ phase: "loading" });
  const [freshKeys, setFreshKeys] = useState<ReadonlySet<string>>(() => new Set());
  // null until the first successful load — the first paint blinks nothing.
  const knownKeysRef = useRef<Set<string> | null>(null);

  const poll = useCallback(async () => {
    const result = await fetchHeartbeatDecisions({ limit: MAX_ROWS });
    if (!result.ok) {
      setState({ phase: "ready", result });
      return;
    }
    const payload = Array.isArray(result.data?.decisions) ? result.data.decisions : [];
    const sorted = sortDecisionsNewestFirst(payload);
    // Dedupe on the stable identity so React row keys stay unique.
    const seen = new Set<string>();
    const rows: HeartbeatDecision[] = [];
    for (const decision of sorted) {
      const key = decisionKey(decision);
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push(decision);
      if (rows.length >= MAX_ROWS) break;
    }
    setFreshKeys(findNewDecisionKeys(knownKeysRef.current, rows));
    knownKeysRef.current = seen;
    setState({ phase: "ready", result: { ok: true, data: { decisions: rows } } });
  }, []);

  useEffect(() => {
    void poll();
    const interval = setInterval(() => void poll(), pollMs);
    return () => clearInterval(interval);
  }, [poll, pollMs]);

  const response = state.phase === "ready" ? state.result : null;
  const rows = response?.ok ? response.data.decisions : [];
  const streamDot =
    state.phase === "loading"
      ? "bg-muted-2"
      : response?.ok
        ? "bg-accent animate-pulse-soft"
        : "bg-danger";

  return (
    <section
      aria-label="Pod decision log"
      className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-mono text-[12px] font-black uppercase tracking-[0.14em] text-text">
            Decision log
          </h2>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2">
            GET /api/v1/heartbeat/decisions
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted">
          <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", streamDot)} />
          {`live · ${Math.round(pollMs / 1000)}s poll`}
        </span>
      </header>

      <div className="bg-bg/60 p-2 font-mono text-[11px] leading-relaxed">
        {state.phase === "loading" ? (
          <div className="space-y-1.5 p-1" aria-hidden>
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton h-6 w-full" />
            ))}
          </div>
        ) : response && !response.ok ? (
          <TerminalUnavailable reason={response.reason} />
        ) : rows.length === 0 ? (
          <p className="px-3 py-6 text-center text-muted">
            No decisions logged yet — rows stream in as pod rules fire.
          </p>
        ) : (
          <ul role="log" aria-live="polite" className="space-y-1">
            {rows.map((decision) => {
              const key = decisionKey(decision);
              return (
                <DecisionRow
                  key={key}
                  decision={decision}
                  fresh={freshKeys.has(key)}
                />
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}

/** Action badge colors — the existing green/red trade tokens, muted otherwise. */
const ACTION_BADGE: Record<DecisionActionTone, string> = {
  buy: "bg-primary-dim text-primary",
  sell: "bg-danger-dim text-danger",
  neutral: "bg-surface-3 text-muted",
};

/** One-shot blink for a row that just streamed in, tinted by its side. */
const FRESH_ANIMATION: Record<DecisionActionTone, string> = {
  buy: "animate-flash-green",
  sell: "animate-flash-red",
  neutral: "animate-ticker-in",
};

function DecisionRow({
  decision,
  fresh,
}: {
  decision: HeartbeatDecision;
  fresh: boolean;
}) {
  const tone = decisionActionTone(decision.action);
  const latency = Number.isFinite(decision.latency_ms)
    ? `${Math.round(decision.latency_ms)}ms`
    : "—";
  return (
    <li
      className={cn(
        "flex items-center gap-2 rounded px-2 py-1",
        fresh && FRESH_ANIMATION[tone],
      )}
    >
      <span className="shrink-0 tabular-nums text-muted-2">
        {formatDecisionTime(decision.t)}
      </span>
      <span className="max-w-[28%] shrink-0 truncate font-bold text-text">
        {decision.pod}
      </span>
      <span className="min-w-0 flex-1 truncate text-muted">{decision.market}</span>
      <span className="shrink-0 rounded border border-border bg-surface-3 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.1em] text-muted">
        {decision.rule}
      </span>
      <span
        className={cn(
          "shrink-0 rounded px-1.5 py-0.5 text-[9px] font-black uppercase tracking-[0.1em]",
          ACTION_BADGE[tone],
        )}
      >
        {decision.action}
      </span>
      <span className="shrink-0 tabular-nums text-muted-2">{latency}</span>
    </li>
  );
}

function TerminalUnavailable({
  reason,
}: {
  reason: "not-deployed" | "unavailable";
}) {
  const notDeployed = reason === "not-deployed";
  return (
    <div className="px-3 py-6 text-center">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-muted-2">
        {notDeployed ? "Decision log not yet deployed" : "Decision stream unavailable"}
      </p>
      <p className="mx-auto mt-1.5 max-w-md text-[11px] normal-case text-muted">
        {notDeployed
          ? "The heartbeat endpoint returned 404 — the backend is still shipping. Rows appear here as soon as it exists; nothing is mocked."
          : "The heartbeat endpoint could not be reached. The next poll retries automatically; no synthetic rows are shown."}
      </p>
    </div>
  );
}
