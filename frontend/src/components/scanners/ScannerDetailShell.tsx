"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ScannerCanvas } from "@/components/scanners/ScannerCanvas";
import { ScannerStatusPill } from "@/components/scanners/ScannerStatusPill";
import { PageShell } from "@/components/ui/kit";
import { useToast } from "@/components/ToastProvider";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/cn";
import {
  getScanner,
  listScannerRuns,
  pauseScanner,
  publishScanner,
  relativeTimeLabel,
  resumeScanner,
  runDurationLabel,
  runScannerNow,
  scheduleLabel,
  testEmailScanner,
  testRunScanner,
  type ApiSource,
  type Scanner,
  type ScannerCandidate,
  type ScannerReads,
  type ScannerRun,
  type ScannerStepType,
  type StepDirection,
} from "@/lib/scanners-api";

/*
 * Loop V84 (U3) — /scanners/[id] detail. Header with status + controls, the
 * React Flow pipeline canvas (TerminalCanvas styling), the latest run result
 * (candidates table with per-step read pills + aligned checkmark, top pick
 * highlighted) and the runs history. Every PnL-ish number is labeled paper.
 */

// ---------------------------------------------------------------------------
// Read pills — one compact chip per spec step, colored by direction.
// Directional arrows: up = mint, down = blue, flat = muted. Never red.
// ---------------------------------------------------------------------------

function directionGlyph(dir: StepDirection): string {
  return dir === "up" ? "↑" : dir === "down" ? "↓" : "·";
}

function directionClasses(dir: StepDirection): string {
  if (dir === "up") return "border-primary/30 bg-primary/10 text-primary";
  if (dir === "down") return "border-secondary/30 bg-secondary/10 text-secondary";
  return "border-border bg-surface-2/60 text-muted";
}

function readPill(
  stepType: ScannerStepType,
  reads: ScannerReads,
): { label: string; dir: StepDirection; paper?: boolean } | null {
  switch (stepType) {
    case "WHALE_FLOW": {
      const r = reads.WHALE_FLOW;
      if (!r) return null;
      return { label: `flow ${directionGlyph(r.direction)} ${r.event_count} ev`, dir: r.direction };
    }
    case "PRICE_TREND": {
      const r = reads.PRICE_TREND;
      if (!r) return null;
      const change =
        r.change === null ? "n/a" : `${r.change > 0 ? "+" : ""}${(r.change * 100).toFixed(1)}%`;
      return { label: `trend ${directionGlyph(r.direction)} ${change}`, dir: r.direction };
    }
    case "NEWS_SENTIMENT": {
      const r = reads.NEWS_SENTIMENT;
      if (!r) return null;
      const score = r.sentiment_score === null ? "n/a" : r.sentiment_score.toFixed(2);
      return { label: `news ${directionGlyph(r.direction)} ${score}`, dir: r.direction };
    }
    case "MODEL_EDGE": {
      const r = reads.MODEL_EDGE;
      if (!r) return null;
      const edge =
        r.edge === null ? "n/a" : `${r.edge > 0 ? "+" : ""}${r.edge.toFixed(2)}`;
      return { label: `model ${directionGlyph(r.direction)} ${edge}`, dir: r.direction, paper: true };
    }
    case "DIRECTION_ALIGNMENT":
      return null; // alignment renders as the checkmark column, not a pill
  }
}

function ReadPills({
  stepTypes,
  candidate,
}: {
  stepTypes: ScannerStepType[];
  candidate: ScannerCandidate;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {stepTypes.map((type) => {
        const pill = readPill(type, candidate.reads);
        if (!pill) return null;
        return (
          <span
            key={type}
            className={cn(
              "inline-flex items-center whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[9.5px] font-bold",
              directionClasses(pill.dir),
            )}
          >
            {pill.label}
            {pill.paper ? <span className="ml-1 text-[8px] uppercase opacity-70">paper</span> : null}
          </span>
        );
      })}
    </div>
  );
}

function AlignedCheck({ aligned }: { aligned: boolean }) {
  return aligned ? (
    <span
      aria-label="directions aligned"
      className="grid h-5 w-5 place-items-center rounded-full border border-primary/40 bg-primary/10 text-[11px] font-black text-primary"
    >
      ✓
    </span>
  ) : (
    <span
      aria-label="not aligned"
      className="grid h-5 w-5 place-items-center rounded-full border border-border bg-surface-2/60 text-[11px] text-muted-2"
    >
      —
    </span>
  );
}

// ---------------------------------------------------------------------------
// Run status chip (history + latest-run header). Same no-red rule:
// completed = mint, running = blue, empty/failed = gray.
// ---------------------------------------------------------------------------

function runStatusClasses(status: ScannerRun["status"]): string {
  if (status === "completed") return "border-primary/40 bg-primary/10 text-primary";
  if (status === "running") return "border-secondary/40 bg-secondary/10 text-secondary";
  return "border-border-light bg-surface-2 text-muted";
}

function RunStatusChip({ status }: { status: ScannerRun["status"] }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em]",
        runStatusClasses(status),
      )}
    >
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "completed" && "bg-primary",
          status === "running" && "animate-pulse bg-secondary",
          (status === "empty" || status === "failed") && "bg-muted-2",
        )}
      />
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Detail shell
// ---------------------------------------------------------------------------

// Loop V86 (X1) — pre-publish flow for draft scanners. A "Test & publish"
// panel: run a test snapshot (amber-tinted candidates table + TEST RUN badge),
// send a test email (sent / not-configured toast), then publish — disabled
// until a test run exists, surfacing the backend's 409 "run a test first"
// when clicked early. Never red; amber (gold) is the test accent.

function PrePublishPanel({
  scanner,
  stepTypes,
  runs,
  token,
  onPublished,
  onTested,
}: {
  scanner: Scanner;
  stepTypes: ScannerStepType[];
  runs: ScannerRun[];
  token: string | null;
  onPublished: (scanner: Scanner) => void;
  onTested: () => void;
}) {
  const { toast } = useToast();
  const [testing, setTesting] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishMsg, setPublishMsg] = useState<string | null>(null);

  // Newest test run (is_test) across history + any just-run local snapshot.
  const testRun = runs.find((r) => r.is_test) ?? null;
  const testResult = testRun?.result ?? null;
  const canPublish = Boolean(testRun);

  async function handleTest() {
    setTesting(true);
    setPublishMsg(null);
    try {
      const { run } = await testRunScanner(scanner.id, token);
      if (!run) {
        toast({ title: "Test run failed", tone: "error" });
      } else {
        await onTested();
      }
    } finally {
      setTesting(false);
    }
  }

  async function handleEmail() {
    setEmailing(true);
    try {
      const res = await testEmailScanner(scanner.id, token);
      if (res.configured && res.sent) {
        toast({ title: "Test email sent", body: "Check the inbox wired to delivery.", tone: "success" });
      } else if (res.configured) {
        toast({ title: "Email configured", body: "Delivery is wired but the test dispatch did not confirm.", tone: "info" });
      } else {
        toast({ title: "Email not configured", body: "Enable email delivery in the spec to send previews.", tone: "info" });
      }
    } finally {
      setEmailing(false);
    }
  }

  async function handlePublish() {
    setPublishing(true);
    setPublishMsg(null);
    try {
      const res = await publishScanner(scanner.id, token);
      if (res.ok) {
        onPublished(res.scanner);
        toast({ title: "Published", body: "Scanner is now active and scheduled.", tone: "success" });
      } else {
        // 409 path — surface the backend's "run a test first" verbatim.
        setPublishMsg(res.message);
      }
    } finally {
      setPublishing(false);
    }
  }

  return (
    <section
      className="t-rise t-stagger-1 mt-5 rounded-xl border border-gold/40 bg-gold/5 p-4"
      aria-label="Test and publish"
      data-testid="scanner-prepublish"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-black tracking-tight text-text">
          Test &amp; publish
        </h2>
        <span className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-gold">
          draft · not scheduled
        </span>
      </div>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">
        Run a paper snapshot over the current universe, preview the email, then
        publish to flip this scanner active. Test runs never fire delivery or
        create orders — paper research only.
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void handleTest()}
          disabled={testing}
          data-testid="scanner-test-run"
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-gold/45 bg-gold/10 px-4 text-[13px] font-bold text-gold shadow-glow transition hover:brightness-110 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M6 4.5v15l13-7.5-13-7.5z" />
          </svg>
          {testing ? "Testing…" : "Run test"}
        </button>
        <button
          type="button"
          onClick={() => void handleEmail()}
          disabled={emailing}
          data-testid="scanner-test-email"
          className="inline-flex h-9 items-center rounded-lg border border-border px-4 text-[13px] font-semibold text-muted transition hover:border-border-light hover:text-text active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none"
        >
          {emailing ? "Sending…" : "Send test email"}
        </button>
        <button
          type="button"
          onClick={() => void handlePublish()}
          disabled={publishing}
          data-testid="scanner-publish"
          aria-disabled={!canPublish}
          title={canPublish ? "Publish — flip this scanner active" : "Run a test first to enable publish"}
          className={cn(
            "inline-flex h-9 items-center gap-2 rounded-lg px-4 text-[13px] font-bold transition active:scale-95",
            "motion-reduce:transform-none disabled:cursor-not-allowed",
            canPublish
              ? "bg-primary text-bg shadow-glow hover:brightness-110 disabled:opacity-40"
              : "border border-border bg-surface-2/60 text-muted-2 opacity-70",
          )}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M12 2l2.39 4.84L20 7.27l-3.5 3.41.83 4.82L12 13l-5.33 2.5L7.5 10.68 4 7.27l5.61-.43L12 2z" />
          </svg>
          {publishing ? "Publishing…" : "Publish"}
        </button>
      </div>

      {!canPublish ? (
        <p className="mt-3 text-[11.5px] text-muted-2">
          Run a test to enable publish{publishMsg ? " — " : ""}{publishMsg ?? ""}
        </p>
      ) : null}
      {publishMsg && canPublish ? (
        <p className="mt-3 rounded-lg border border-gold/30 bg-gold/5 px-3 py-2 text-[11.5px] text-gold">
          {publishMsg}
        </p>
      ) : null}

      {/* Test result — candidates table, TEST RUN badge, amber tint. */}
      {testRun && testResult ? (
        <div
          data-testid="scanner-test-result"
          className="mt-4 rounded-xl border border-gold/35 bg-gold/5 p-3.5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-gold/45 bg-gold/15 px-2 py-0.5 font-mono text-[10px] font-black uppercase tracking-[0.14em] text-gold">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-gold" />
              Test run
            </span>
            <span className="font-mono text-[11px] text-muted-2">
              {relativeTimeLabel(testRun.started_at)} · {runDurationLabel(testRun)}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em]">
            <span className="rounded border border-border bg-bg/60 px-2 py-1 text-muted">
              universe {testResult.counts.universe}
            </span>
            <span className="rounded border border-border bg-bg/60 px-2 py-1 text-muted">
              candidates {testResult.counts.candidates}
            </span>
            <span className="rounded border border-gold/30 bg-gold/10 px-2 py-1 text-gold">
              aligned {testResult.counts.aligned}
            </span>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table
              data-testid="scanner-test-candidates"
              className="w-full min-w-[420px] border-collapse text-left"
            >
              <thead>
                <tr className="border-b border-border font-mono text-[9.5px] font-bold uppercase tracking-[0.14em] text-muted-2">
                  <th className="pb-2 pr-3">Market</th>
                  <th className="pb-2 pr-3">Step reads</th>
                  <th className="pb-2 text-center">Aligned</th>
                </tr>
              </thead>
              <tbody>
                {testResult.candidates.map((cand) => (
                  <tr
                    key={cand.market_slug}
                    className="border-b border-border/50 align-top transition hover:bg-surface-2/40"
                  >
                    <td className="max-w-[200px] py-2.5 pr-3">
                      <span className="block truncate text-[12.5px] font-bold text-text">
                        {cand.title}
                      </span>
                      <span className="block truncate font-mono text-[9.5px] text-muted-2">
                        {cand.market_slug}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3">
                      <ReadPills stepTypes={stepTypes} candidate={cand} />
                    </td>
                    <td className="py-2.5 text-center">
                      <AlignedCheck aligned={cand.aligned} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div aria-busy="true">
      <div className="t-skeleton h-5 w-32" />
      <div className="t-skeleton mt-4 h-9 w-2/3" />
      <div className="t-skeleton mt-3 h-4 w-1/3" />
      <div className="t-skeleton mt-6 h-[520px] w-full rounded-xl" />
      <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="t-skeleton h-64 rounded-xl" />
        <div className="t-skeleton h-64 rounded-xl" />
      </div>
    </div>
  );
}

export function ScannerDetailShell({ id }: { id: string }) {
  const { token, isReady } = useAuth();
  const [scanner, setScanner] = useState<Scanner | null | undefined>(undefined);
  const [runs, setRuns] = useState<ScannerRun[]>([]);
  const [source, setSource] = useState<ApiSource>("mock");
  const [running, setRunning] = useState(false);
  // X1: spring the status pill the moment a draft publishes to active.
  const [popStatus, setPopStatus] = useState(false);

  useEffect(() => {
    if (!isReady) return;
    let dead = false;
    void (async () => {
      const [scannerRes, runsRes] = await Promise.all([
        getScanner(id, token),
        listScannerRuns(id, token),
      ]);
      if (dead) return;
      setScanner(scannerRes.scanner);
      setSource(scannerRes.source);
      setRuns(runsRes.runs);
    })();
    return () => {
      dead = true;
    };
  }, [id, token, isReady]);

  const refresh = useCallback(async () => {
    const [scannerRes, runsRes] = await Promise.all([
      getScanner(id, token),
      listScannerRuns(id, token),
    ]);
    if (scannerRes.scanner) setScanner(scannerRes.scanner);
    setRuns(runsRes.runs);
  }, [id, token]);

  async function handleRun() {
    setRunning(true);
    try {
      await runScannerNow(id, token);
      await refresh();
    } finally {
      setRunning(false);
    }
  }

  async function handlePause() {
    const { scanner: updated } = await pauseScanner(id, token);
    if (updated) setScanner(updated);
  }

  async function handleResume() {
    const { scanner: updated } = await resumeScanner(id, token);
    if (updated) setScanner(updated);
  }

  // X1: publish flips draft -> active; spring the pill once on success.
  function handlePublished(updated: Scanner) {
    setScanner(updated);
    if (updated.status === "active") {
      setPopStatus(true);
      window.setTimeout(() => setPopStatus(false), 600);
    }
  }

  if (scanner === undefined) {
    return (
      <PageShell width="wide">
        <div data-testid="scanner-detail-page">
          <DetailSkeleton />
        </div>
      </PageShell>
    );
  }

  if (scanner === null) {
    return (
      <PageShell width="wide">
        <div data-testid="scanner-detail-page" className="py-16 text-center">
          <p className="text-lg font-black text-text">Scanner not found</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            This scanner does not exist or is not visible to you. It may have been created in
            another account.
          </p>
          <Link
            href="/scanners"
            className="mt-5 inline-flex h-9 items-center rounded-lg bg-primary px-4 text-[13px] font-bold text-bg shadow-glow transition hover:brightness-110"
          >
            ← Back to Scanner Studio
          </Link>
        </div>
      </PageShell>
    );
  }

  const paused = scanner.status === "paused";
  const latestRun = scanner.latest_run;
  const result = latestRun?.result ?? null;
  const stepTypes = scanner.spec.steps.map((s) => s.type);
  const topPick = result?.top_pick ?? null;

  return (
    <PageShell width="wide">
      <div data-testid="scanner-detail-page">
        <Link
          href="/scanners"
          className="font-mono text-[11px] font-bold uppercase tracking-[0.12em] text-muted-2 transition hover:text-primary"
        >
          ← All scanners
        </Link>

        {/* Header: name, status pill, run controls, spec meta. */}
        <header className="t-rise mt-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="min-w-0 flex-1 truncate text-2xl font-black tracking-tight text-text sm:text-3xl">
              {scanner.name}
            </h1>
            <ScannerStatusPill status={scanner.status} className={popStatus ? "scanner-status-pop" : undefined} />
            <span
              data-testid="scanner-detail-source"
              className="rounded-full border border-border bg-surface px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted"
            >
              {source === "live" ? "live API" : "mock data"}
            </span>
          </div>
          {scanner.description ? (
            <p className="mt-1.5 max-w-2xl text-sm text-muted">{scanner.description}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void handleRun()}
              disabled={running || paused}
              data-testid="scanner-detail-run"
              title={paused ? "Resume the scanner to run it" : "Run this scanner now (paper)"}
              className={cn(
                "inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-4 text-[13px] font-bold text-bg shadow-glow transition hover:brightness-110 active:scale-95",
                "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
              )}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <path d="M6 4.5v15l13-7.5-13-7.5z" />
              </svg>
              {running ? "Running…" : "Run now"}
            </button>
            <button
              type="button"
              onClick={() => void (paused ? handleResume() : handlePause())}
              disabled={running || scanner.status === "draft"}
              data-testid="scanner-detail-pause"
              className={cn(
                "inline-flex h-9 items-center rounded-lg border border-border px-4 text-[13px] font-semibold text-muted transition hover:border-border-light hover:text-text active:scale-95",
                "disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transform-none",
              )}
            >
              {paused ? "Resume" : "Pause"}
            </button>
            <span className="ml-auto font-mono text-[11px] font-bold text-muted">
              {scheduleLabel(scanner.spec)} · {scanner.spec.schedule.timezone} ·{" "}
              {scanner.spec.universe.categories.length > 0
                ? scanner.spec.universe.categories.join(" · ")
                : "all markets"}{" "}
              · v{scanner.version}
            </span>
          </div>
        </header>

        <p
          data-testid="scanner-detail-paper-banner"
          className="mt-5 rounded-lg border border-primary/25 bg-primary-dim/40 px-3 py-2 font-mono text-[10.5px] font-bold uppercase tracking-[0.12em] text-primary"
        >
          Paper research only — reads are simulated signals, never orders.
        </p>

        {scanner.status === "draft" ? (
          <PrePublishPanel
            scanner={scanner}
            stepTypes={stepTypes}
            runs={runs}
            token={token}
            onPublished={handlePublished}
            onTested={refresh}
          />
        ) : null}

        {/* THE CANVAS — spec pipeline, TerminalCanvas styling. */}
        <section className="t-rise t-stagger-1 mt-5" aria-label="Scanner pipeline">
          <div className="mb-2 flex items-end justify-between gap-3">
            <h2 className="text-base font-black tracking-tight text-text">Pipeline</h2>
            <span className="font-mono text-[11px] font-bold text-muted-2">
              {scanner.spec.steps.length} steps · left → right
            </span>
          </div>
          <ScannerCanvas steps={scanner.spec.steps} latestRun={latestRun} />
        </section>

        {/* Latest run result + runs history. */}
        <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section
            className="t-rise t-stagger-2 min-w-0 rounded-xl border border-border bg-surface p-4"
            aria-label="Latest run result"
            data-testid="scanner-latest-run"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-black tracking-tight text-text">Latest run</h2>
              {latestRun ? (
                <div className="flex items-center gap-2 font-mono text-[11px] text-muted">
                  <RunStatusChip status={latestRun.status} />
                  <span>{relativeTimeLabel(latestRun.started_at)}</span>
                  <span className="text-muted-2">{runDurationLabel(latestRun)}</span>
                </div>
              ) : null}
            </div>

            {!latestRun ? (
              <p className="mt-4 text-[13px] text-muted">
                No runs yet — press Run now to execute the pipeline over the current universe.
              </p>
            ) : latestRun.error ? (
              <p className="mt-4 rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-[12px] text-muted">
                Run failed: {latestRun.error}
              </p>
            ) : !result || result.candidates.length === 0 ? (
              <p className="mt-4 text-[13px] text-muted">
                Empty run — the universe filter matched no open markets. Widen categories or lower
                the minimum volume.
              </p>
            ) : (
              <>
                {/* Counts strip */}
                <div className="mt-3 flex flex-wrap gap-2 font-mono text-[10px] font-bold uppercase tracking-[0.1em]">
                  <span className="rounded border border-border bg-bg/60 px-2 py-1 text-muted">
                    universe {result.counts.universe}
                  </span>
                  <span className="rounded border border-border bg-bg/60 px-2 py-1 text-muted">
                    candidates {result.counts.candidates}
                  </span>
                  <span className="rounded border border-primary/30 bg-primary/10 px-2 py-1 text-primary">
                    aligned {result.counts.aligned}
                  </span>
                </div>

                {/* Top pick — highlighted, labeled paper. */}
                {topPick ? (
                  <div
                    data-testid="scanner-top-pick"
                    className="mt-4 rounded-xl border border-primary/45 bg-primary-dim/30 p-3.5 shadow-glow"
                  >
                    <p className="font-mono text-[9px] font-black uppercase tracking-[0.16em] text-primary">
                      Top pick · paper research
                    </p>
                    <p className="mt-1 text-[14px] font-black tracking-tight text-text">
                      {topPick.title}
                    </p>
                    <p className="font-mono text-[10px] text-muted-2">{topPick.market_slug}</p>
                    <div className="mt-2">
                      <ReadPills stepTypes={stepTypes} candidate={topPick} />
                    </div>
                  </div>
                ) : null}

                {/* Candidates table */}
                <div className="mt-4 overflow-x-auto">
                  <table
                    data-testid="scanner-candidates"
                    className="w-full min-w-[480px] border-collapse text-left"
                  >
                    <thead>
                      <tr className="border-b border-border font-mono text-[9.5px] font-bold uppercase tracking-[0.14em] text-muted-2">
                        <th className="pb-2 pr-3">Market</th>
                        <th className="pb-2 pr-3">Step reads</th>
                        <th className="pb-2 text-center">Aligned</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.candidates.map((cand) => (
                        <tr
                          key={cand.market_slug}
                          className={cn(
                            "border-b border-border/50 align-top transition hover:bg-surface-2/40",
                            topPick?.market_slug === cand.market_slug && "bg-primary-dim/20",
                          )}
                        >
                          <td className="max-w-[220px] py-2.5 pr-3">
                            <span className="block truncate text-[12.5px] font-bold text-text">
                              {cand.title}
                            </span>
                            <span className="block truncate font-mono text-[9.5px] text-muted-2">
                              {cand.market_slug}
                            </span>
                          </td>
                          <td className="py-2.5 pr-3">
                            <ReadPills stepTypes={stepTypes} candidate={cand} />
                          </td>
                          <td className="py-2.5 text-center">
                            <AlignedCheck aligned={cand.aligned} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 text-[10.5px] leading-relaxed text-muted-2">
                  All values are paper research reads from the mirrored market catalog —
                  simulated, research-only, never investment advice or an order path.
                </p>
              </>
            )}
          </section>

          {/* Runs history rail */}
          <section
            className="t-rise t-stagger-3 min-w-0 rounded-xl border border-border bg-surface p-4"
            aria-label="Runs history"
            data-testid="scanner-runs-history"
          >
            <div className="flex items-end justify-between gap-3">
              <h2 className="text-base font-black tracking-tight text-text">Runs</h2>
              <span className="font-mono text-[11px] font-bold text-muted-2">
                last {runs.length}
              </span>
            </div>
            {runs.length === 0 ? (
              <p className="mt-3 text-[12.5px] text-muted">No runs recorded yet.</p>
            ) : (
              <ul className="mt-3 space-y-1.5">
                {runs.map((run) => (
                  <li
                    key={run.id}
                    data-testid="scanner-run-row"
                    className="flex items-center gap-2 rounded-lg border border-border/60 bg-bg/50 px-2.5 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <span className="block font-mono text-[11px] font-bold text-text">
                        {relativeTimeLabel(run.started_at)}
                      </span>
                      <span className="block font-mono text-[9.5px] text-muted-2">
                        {run.started_at.replace("T", " ").slice(0, 19)} UTC
                      </span>
                    </div>
                    <RunStatusChip status={run.status} />
                    <span className="w-12 text-right font-mono text-[10.5px] font-bold text-muted">
                      {runDurationLabel(run)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </PageShell>
  );
}
