"use client";

import { useCallback, useEffect, useState } from "react";

import { DecisionLogTerminal } from "@/components/DecisionLogTerminal";
import { PodEquitySparkline } from "@/components/PodEquitySparkline";
import { PageHeader, PageShell } from "@/components/ui/kit";
import { relativeTime } from "@/lib/alerts-api";
import { cn } from "@/lib/cn";
import { formatUSD } from "@/lib/mock-data";
import {
  fetchPods,
  normalizePodStatus,
  type PodsApiResult,
  type PodsResponse,
  type PodSummary,
} from "@/lib/pods-api";

/**
 * Loop V60 (U2) — /pods fleet dashboard. Read-only paper-trading telemetry:
 * pod cards with equity sparklines and status chips. If the pods backend is
 * not deployed yet (404) the page says so honestly — no fabricated fleet
 * numbers, ever.
 */

const PAPER_BANNER =
  "Simulated funds — no execution. Pod balances, equity curves, and decisions are paper-trading telemetry only.";

/** Last-decision label: em-dash when missing or unparseable. */
function formatLastDecisionAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  return relativeTime(iso) || "—";
}

type LoadState =
  | { phase: "loading" }
  | { phase: "ready"; result: PodsApiResult<PodsResponse> };

export default function PodsPage() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (initial: boolean) => {
    if (initial) {
      setState({ phase: "loading" });
    } else {
      setRefreshing(true);
    }
    const result = await fetchPods();
    setState({ phase: "ready", result });
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void load(true);
  }, [load]);

  const response = state.phase === "ready" ? state.result : null;
  const pods = response?.ok ? response.data.pods : [];
  const curves = response?.ok ? response.data.equity_curves : {};

  return (
    <PageShell width="wide">
      <PageHeader
        kicker="Paper fleet telemetry"
        title="Pods"
        subtitle="Command center for the paper-trading pod fleet — equity, status, and per-pod telemetry."
        actions={
          <button
            type="button"
            onClick={() => void load(false)}
            disabled={state.phase === "loading" || refreshing}
            className="h-10 rounded-xl border border-border px-4 text-sm font-bold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        }
      />

      {/* Honest paper-trading banner — simulated funds, no execution. */}
      <div className="mb-6 flex items-center gap-3 rounded-2xl border border-accent/30 bg-accent-dim/40 px-4 py-3">
        <span
          aria-hidden
          className="inline-block h-2 w-2 shrink-0 rounded-full bg-accent shadow-[0_0_10px_rgba(0,201,160,0.8)]"
        />
        <p className="text-sm font-semibold text-accent">{PAPER_BANNER}</p>
      </div>

      {state.phase === "loading" ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-56 w-full" />
          ))}
        </div>
      ) : response && !response.ok ? (
        <PodsUnavailable reason={response.reason} onRetry={() => void load(false)} />
      ) : pods.length === 0 ? (
        <section className="rounded-2xl border border-border bg-surface p-8 text-center">
          <p className="text-lg font-semibold text-text">No pods registered yet</p>
          <p className="mt-2 text-sm text-muted">
            The fleet endpoint is live but reports zero pods. Cards appear here as
            soon as the first pod checks in.
          </p>
        </section>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {pods.map((pod) => (
            <PodCard key={pod.id} pod={pod} curve={curves[pod.id] ?? []} />
          ))}
        </div>
      )}

      {/* U3 — live decision-log terminal (independent endpoint; renders its
          own honest states regardless of the fleet state above). */}
      <div className="mt-6">
        <DecisionLogTerminal />
      </div>
    </PageShell>
  );
}

function PodsUnavailable({
  reason,
  onRetry,
}: {
  reason: "not-deployed" | "unavailable";
  onRetry: () => void;
}) {
  const notDeployed = reason === "not-deployed";
  return (
    <section className="rounded-2xl border border-border bg-surface p-8 text-center">
      <p className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-muted-2">
        GET /api/v1/pods
      </p>
      <p className="mt-2 text-lg font-semibold text-text">
        {notDeployed ? "Pods API not yet deployed" : "Pods telemetry unavailable"}
      </p>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">
        {notDeployed
          ? "The pods endpoint returned 404 — the backend is still shipping. This page renders live fleet data as soon as it exists; nothing here is mocked."
          : "The pods endpoint could not be reached. No cached or synthetic fleet data is shown."}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-xl border border-border px-4 py-2 text-sm font-bold text-text transition hover:border-accent hover:text-accent"
      >
        Retry
      </button>
    </section>
  );
}

const STATUS_CHIP: Record<string, { label: string; className: string; pulse?: boolean }> = {
  running: {
    label: "running",
    className: "border-primary/40 bg-primary-dim/55 text-primary",
    pulse: true,
  },
  halted: {
    label: "halted",
    className: "border-danger/40 bg-danger-dim text-danger",
  },
  "flag-off": {
    label: "flag-off",
    className: "border-border bg-surface-3 text-muted",
  },
  unknown: {
    label: "unknown",
    className: "border-border bg-surface-3 text-muted",
  },
};

function PodStatusChip({ status }: { status: string }) {
  const kind = normalizePodStatus(status);
  const chip = STATUS_CHIP[kind] ?? STATUS_CHIP.unknown!;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.12em]",
        chip.className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "inline-block h-1.5 w-1.5 rounded-full bg-current",
          chip.pulse && "animate-pulse",
        )}
      />
      {chip.label}
    </span>
  );
}

function PodCard({ pod, curve }: { pod: PodSummary; curve: PodsResponse["equity_curves"][string] }) {
  const pnl = pod.pnl_24h;
  const pnlTone = pnl > 0 ? "text-primary" : pnl < 0 ? "text-danger" : "text-muted";
  return (
    <section className="rounded-2xl border border-border bg-surface p-4 shadow-card sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-mono text-sm font-black tracking-tight text-text">
            {pod.name}
          </h2>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-2">
            {pod.id}
          </p>
        </div>
        <PodStatusChip status={pod.status} />
      </div>

      <div className="mt-3 flex items-baseline gap-3">
        <span className="font-mono text-2xl font-black tabular-nums text-text">
          {formatUSD(pod.equity)}
        </span>
        <span className={cn("font-mono text-sm font-bold tabular-nums", pnlTone)}>
          {pnl > 0 ? "+" : pnl < 0 ? "-" : ""}
          {formatUSD(Math.abs(pnl))} 24h
        </span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3">
        <PodStat label="Bankroll" value={formatUSD(pod.bankroll)} />
        <PodStat label="Trades" value={pod.trades_count.toLocaleString()} />
        <PodStat
          label="Last decision"
          value={formatLastDecisionAt(pod.last_decision_at)}
        />
      </div>

      <div className="mt-3">
        <PodEquitySparkline points={curve} podName={pod.name} />
      </div>
    </section>
  );
}

function PodStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted-2">{label}</p>
      <p className="mt-0.5 truncate font-mono text-xs font-bold tabular-nums text-muted">
        {value}
      </p>
    </div>
  );
}
