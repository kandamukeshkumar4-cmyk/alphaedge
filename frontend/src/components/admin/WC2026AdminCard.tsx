"use client";

import { useCallback, useEffect, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import {
  fetchWC2026Status,
  resolveWC2026Markets,
  seedWC2026Markets,
  type WC2026Status,
} from "@/lib/admin-dashboard-api";

type WC2026AdminCardProps = {
  apiKey: string;
};

export function WC2026AdminCard({ apiKey }: WC2026AdminCardProps) {
  const { toast } = useToast();
  const [status, setStatus] = useState<WC2026Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    if (!apiKey.trim()) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const result = await fetchWC2026Status(apiKey);
    setLoading(false);
    if (!result.ok) {
      setError(result.message);
      setStatus(null);
      return;
    }
    setStatus(result.data);
  }, [apiKey]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  async function handleSeed() {
    setSeeding(true);
    const result = await seedWC2026Markets(apiKey);
    setSeeding(false);
    if (!result.ok) {
      toast({ title: "Seed failed", body: result.message, tone: "error" });
      return;
    }
    toast({
      title: "Markets seeded",
      body: `Created ${result.data.created}, skipped ${result.data.skipped}`,
      tone: "success",
    });
    await loadStatus();
  }

  async function handleResolve() {
    setResolving(true);
    const result = await resolveWC2026Markets(apiKey);
    setResolving(false);
    if (!result.ok) {
      toast({ title: "Resolution failed", body: result.message, tone: "error" });
      return;
    }
    toast({
      title: "Resolution complete",
      body: `Resolved ${result.data.resolved}, skipped ${result.data.skipped}`,
      tone: "success",
    });
    await loadStatus();
  }

  return (
    <section className="rounded-xl border border-border bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text">⚽ WC2026 Markets</h2>
          {loading ? (
            <p className="mt-2 text-sm text-muted">Loading status…</p>
          ) : error ? (
            <p className="mt-2 text-sm text-danger">{error}</p>
          ) : status ? (
            <div className="mt-3 space-y-1 text-sm text-muted">
              <p>
                {status.total_fixtures} fixtures · {status.seeded} seeded ·{" "}
                {status.resolved} resolved
              </p>
              <p>{status.pending} pending resolution</p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-muted">No status available.</p>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          className="min-h-10 rounded-lg bg-accent px-4 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={seeding || !apiKey.trim()}
          onClick={() => void handleSeed()}
          type="button"
        >
          {seeding ? "Seeding…" : "Seed Markets"}
        </button>
        <button
          className="min-h-10 rounded-lg border border-primary/45 px-4 text-sm font-semibold text-primary transition hover:border-primary hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
          disabled={resolving || !apiKey.trim()}
          onClick={() => void handleResolve()}
          type="button"
        >
          {resolving ? "Running…" : "Run Resolution"}
        </button>
      </div>
    </section>
  );
}
