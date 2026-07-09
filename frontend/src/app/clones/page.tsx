"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { fetchClones, type CloneConfig } from "@/lib/alphaedge-api";
import { CloneCard } from "@/components/clones/CloneCard";

function ClonesPageInner() {
  const { token, isReady } = useAuth();
  const [clones, setClones] = useState<CloneConfig[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isReady) return;
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchClones(token).then((data) => {
      setClones(data);
      setLoading(false);
    });
  }, [token, isReady]);

  return (
    <main className="min-h-screen bg-bg">
      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-text">Agent Clones</h1>
            <p className="mt-1 text-sm text-muted">
              Compose and deploy paper-mode research agents from vetted graph nodes.
              All results are simulation-only.
            </p>
          </div>
          {token && (
            <Link
              href="/clones/new"
              className="shrink-0 rounded-lg bg-accent-bright px-4 py-2 text-sm font-semibold text-bg transition hover:bg-accent"
            >
              + New clone
            </Link>
          )}
        </div>

        {/* Research notice */}
        <div className="mb-6 rounded-xl border border-secondary/30 bg-secondary/5 px-4 py-3 text-xs text-secondary">
          <span className="font-semibold">Research only</span> — clones run on simulated data
          for backtests and track-record study, not live betting, and cannot place real orders.
          All results are provisional until{" "}
          <span className="font-mono">clv_gate_passed=true</span>.
        </div>

        {/* Auth gate */}
        {isReady && !token && (
          <div className="rounded-xl border border-border bg-surface p-8 text-center">
            <p className="text-sm text-muted">
              Please{" "}
              <Link href="/auth/login" className="font-semibold text-accent underline">
                log in
              </Link>{" "}
              to create and manage clones.
            </p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 animate-pulse rounded-xl bg-surface" />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && token && clones.length === 0 && (
          <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center">
            <p className="text-sm font-medium text-text">No clones yet</p>
            <p className="mt-1 text-xs text-muted">
              Build your first agent clone in about 1 minute.
            </p>
            <Link
              href="/clones/new"
              className="mt-4 inline-block rounded-lg bg-accent-bright px-5 py-2 text-sm font-semibold text-bg transition hover:bg-accent"
            >
              Build a clone
            </Link>
          </div>
        )}

        {/* Clone list */}
        {!loading && token && clones.length > 0 && (
          <div className="space-y-3">
            {clones.map((clone) => (
              <CloneCard key={clone.id} clone={clone} token={token} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

export default function ClonesPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-bg">
          <div className="mx-auto max-w-3xl px-4 py-8">
            <div className="h-8 w-48 animate-pulse rounded bg-surface" />
          </div>
        </main>
      }
    >
      <ClonesPageInner />
    </Suspense>
  );
}
