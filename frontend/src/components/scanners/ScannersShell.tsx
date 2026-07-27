"use client";

import { useCallback, useEffect, useState } from "react";

import { ScannerCard } from "@/components/scanners/ScannerCard";
import { ConvergencePanel } from "@/components/scanners/ConvergencePanel";
import { ScannerComposer } from "@/components/scanners/ScannerComposer";
import { PageHeader, PageShell, SegTabs } from "@/components/ui/kit";
import { useAuth } from "@/hooks/useAuth";
import {
  getScanner,
  listScanners,
  pauseScanner,
  resumeScanner,
  runScannerNow,
  type ApiSource,
  type Scanner,
} from "@/lib/scanners-api";

/*
 * Loop V84 (U2) — /scanners list page. Composer hero on top ("Describe a
 * scanner" → compile preview → create), scanner card grid below. Live API
 * first with mock fallback (scanners-api.ts); skeletons reserve card height
 * so the swap in is CLS-free.
 */

/** Fixed-height skeleton card — matches ScannerCard's footprint (no CLS). */
function CardSkeleton() {
  return (
    <div aria-hidden className="h-[224px] rounded-xl border border-border/60 bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="t-skeleton h-4 w-1/2" />
        <div className="t-skeleton h-4 w-16 rounded-full" />
      </div>
      <div className="t-skeleton mt-3 h-3 w-full" />
      <div className="t-skeleton mt-1.5 h-3 w-2/3" />
      <div className="flex gap-1.5">
        <div className="t-skeleton mt-4 h-4 w-12" />
        <div className="t-skeleton mt-4 h-4 w-12" />
        <div className="t-skeleton mt-4 h-4 w-12" />
      </div>
      <div className="t-skeleton mt-4 h-3 w-3/4" />
      <div className="t-skeleton mt-1.5 h-3 w-1/2" />
      <div className="mt-4 flex gap-2 border-t border-border/60 pt-3">
        <div className="t-skeleton h-8 w-24" />
        <div className="t-skeleton h-8 w-20" />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div
      data-testid="scanners-empty"
      className="grid h-[224px] place-items-center rounded-xl border border-dashed border-border bg-surface/40 px-6 text-center"
    >
      <div>
        <p className="text-sm font-bold text-text">No scanners yet</p>
        <p className="mx-auto mt-1.5 max-w-md text-[12.5px] leading-relaxed text-muted">
          Describe one above — whale flow, price trend, news sentiment, model edge — compile the
          spec, and it lands here. Scanners watch markets on a schedule; they never trade.
        </p>
      </div>
    </div>
  );
}

export function ScannersShell() {
  const { token, isReady } = useAuth();
  const [scanners, setScanners] = useState<Scanner[] | null>(null);
  const [source, setSource] = useState<ApiSource>("mock");
  const [runningIds, setRunningIds] = useState<ReadonlySet<string>>(new Set());
  const [activeTab, setActiveTab] = useState<"list" | "convergence">("list");

  useEffect(() => {
    if (!isReady) return;
    let dead = false;
    void listScanners(token).then(({ scanners: list, source: src }) => {
      if (dead) return;
      setScanners(list);
      setSource(src);
    });
    return () => {
      dead = true;
    };
  }, [token, isReady]);

  /** Replace one scanner in the grid (or append when brand new). */
  const upsert = useCallback((updated: Scanner) => {
    setScanners((prev) => {
      if (!prev) return prev;
      return prev.some((s) => s.id === updated.id)
        ? prev.map((s) => (s.id === updated.id ? updated : s))
        : [updated, ...prev];
    });
  }, []);

  const markRunning = useCallback((id: string, running: boolean) => {
    setRunningIds((prev) => {
      const next = new Set(prev);
      if (running) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  async function handleRun(id: string) {
    markRunning(id, true);
    try {
      await runScannerNow(id, token);
      const { scanner } = await getScanner(id, token);
      if (scanner) upsert(scanner);
    } finally {
      markRunning(id, false);
    }
  }

  async function handlePause(id: string) {
    const { scanner } = await pauseScanner(id, token);
    if (scanner) upsert(scanner);
  }

  async function handleResume(id: string) {
    const { scanner } = await resumeScanner(id, token);
    if (scanner) upsert(scanner);
  }

  return (
    <PageShell width="wide">
      <div data-testid="scanners-page">
        <PageHeader
          kicker="Scanner Studio"
          title="Scanners"
          subtitle="Plain-English market monitors compiled into scheduled, step-by-step alert specs. Research only — scanners read markets and never place orders."
          actions={
            scanners !== null ? (
              <span
                data-testid="scanners-source"
                className="rounded-full border border-border bg-surface px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-muted"
              >
                {source === "live" ? "live API" : "mock data"}
              </span>
            ) : undefined
          }
        />

        <div className="mb-6">
          <SegTabs
            value={activeTab}
            onChange={setActiveTab}
            options={[
              { value: "list", label: "My Scanners" },
              { value: "convergence", label: "Convergence" },
            ]}
          />
        </div>

        {activeTab === "list" ? (
          <>
            <ScannerComposer
              token={isReady ? token : null}
              onCreated={(scanner) => upsert(scanner)}
            />

            <div className="mt-8">
              <div className="mb-3 flex items-end justify-between gap-3">
                <h2 className="text-base font-black tracking-tight text-text sm:text-lg">
                  Your scanners
                </h2>
                {scanners !== null ? (
                  <span className="font-mono text-[11px] font-bold text-muted-2">
                    {scanners.length} total
                  </span>
                ) : null}
              </div>

              <p
                data-testid="scanners-paper-banner"
                className="mb-4 rounded-lg border border-primary/25 bg-primary-dim/40 px-3 py-2 font-mono text-[10.5px] font-bold uppercase tracking-[0.12em] text-primary"
              >
                Paper research only — scanner alerts are signals, never orders.
              </p>

              {scanners === null ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true">
                  <CardSkeleton />
                  <CardSkeleton />
                  <CardSkeleton />
                </div>
              ) : scanners.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {scanners.map((scanner, i) => (
                    <ScannerCard
                      key={scanner.id}
                      scanner={scanner}
                      index={i}
                      running={runningIds.has(scanner.id)}
                      onRun={(id) => void handleRun(id)}
                      onPause={(id) => void handlePause(id)}
                      onResume={(id) => void handleResume(id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <ConvergencePanel />
        )}
      </div>
    </PageShell>
  );
}
