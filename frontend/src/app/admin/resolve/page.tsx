"use client";

import { FormEvent, useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
const API = API_BASE;
const ADMIN_API_KEY_STORAGE = "alphaedge.adminApiKey";

const CATALOG_SLUGS = [
  "nba-2025-01-15-lal-bos",
  "nba-warriors-playoff-seed",
  "elect-la-mayor-2026",
  "elect-2028-dem-nominee",
  "wc2026-m1-mex-homewin",
  "wc2026-m1-draw",
  "wc2026-m1-rsa-awaywin",
  "wc2026-winner-brazil",
  "wc2026-winner-france",
  "wc2026-winner-argentina",
  "crypto-btc-friday-5pm",
  "crypto-eth-100k-eoy",
  "culture-gta6-trailer",
  "culture-love-island-elim",
  "econ-cpi-above-3",
  "econ-fed-cut-march",
] as const;

type ResolveOutcome = "YES" | "NO" | "VOID";

type ResolveResponse = {
  slug: string;
  winning_outcome: string;
  settled: number;
  skipped_already_settled: number;
  total_payout: string;
  paper_orders_settled: number;
};

export default function AdminResolvePage() {
  const [slug, setSlug] = useState<string>(CATALOG_SLUGS[0]);
  const [outcome, setOutcome] = useState<ResolveOutcome>("YES");
  const [adminApiKey, setAdminApiKey] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(ADMIN_API_KEY_STORAGE);
      if (stored) {
        setAdminApiKey(stored);
      }
    } catch {
      // sessionStorage unavailable
    }
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    if (!API) {
      setError("Set NEXT_PUBLIC_API_URL to resolve markets.");
      return;
    }
    if (!adminApiKey.trim()) {
      setError("Admin API key is required.");
      return;
    }
    setConfirmOpen(true);
  }

  async function confirmResolve() {
    setConfirmOpen(false);
    setLoading(true);
    setMessage(null);
    setError(null);

    try {
      sessionStorage.setItem(ADMIN_API_KEY_STORAGE, adminApiKey);
    } catch {
      // sessionStorage unavailable
    }

    try {
      const response = await fetch(`${API}/api/v1/admin/markets/${slug}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-API-Key": adminApiKey.trim(),
        },
        body: JSON.stringify({ winning_outcome: outcome }),
      });

      const body = (await response.json().catch(() => ({}))) as ResolveResponse & {
        detail?: string;
      };

      if (!response.ok) {
        setError(body.detail ?? `Request failed (${response.status})`);
        return;
      }

      setMessage(
        `Resolved ${body.slug} as ${body.winning_outcome}. ` +
          `CLOB settled ${body.settled}, paper orders ${body.paper_orders_settled}, ` +
          `payout ${body.total_payout}.`,
      );
    } catch {
      setError("Could not reach the API to resolve this market.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-accent">Admin</p>
        <h1 className="mt-1 text-3xl font-black text-text">Resolve market</h1>
        <p className="mt-2 text-sm text-muted">
          Paper-trading simulation only. Settlement credits simulated balances.
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-2xl border border-border bg-surface p-5"
      >
        <label className="block text-sm">
          <span className="font-semibold text-text">Market slug</span>
          <select
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            className="mt-1 w-full rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm"
          >
            {CATALOG_SLUGS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <fieldset>
          <legend className="text-sm font-semibold text-text">Winning outcome</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {(["YES", "NO", "VOID"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setOutcome(value)}
                className={
                  outcome === value
                    ? "rounded-xl bg-accent px-4 py-2 text-sm font-bold text-bg"
                    : "rounded-xl border border-border px-4 py-2 text-sm font-bold text-muted"
                }
              >
                {value}
              </button>
            ))}
          </div>
        </fieldset>

        <label className="block text-sm">
          <span className="font-semibold text-text">Admin API key</span>
          <input
            type="password"
            value={adminApiKey}
            onChange={(event) => setAdminApiKey(event.target.value)}
            className="mt-1 w-full rounded-xl border border-border bg-surface-2 px-3 py-2 text-sm"
            autoComplete="off"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-accent py-2.5 text-sm font-bold text-bg disabled:opacity-50"
        >
          {loading ? "Resolving…" : "Resolve market"}
        </button>
      </form>

      {message ? (
        <p className="mt-4 rounded-xl border border-primary/30 bg-primary-dim px-4 py-3 text-sm text-primary">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 rounded-xl border border-danger/30 bg-danger-dim px-4 py-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      {confirmOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-lg font-black text-text">Confirm resolution</h2>
            <p className="mt-2 text-sm text-muted">
              Resolve <span className="font-mono text-text">{slug}</span> as{" "}
              <span className="font-bold text-text">{outcome}</span>?
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                className="rounded-xl border border-border px-4 py-2 text-sm font-bold text-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void confirmResolve()}
                className="rounded-xl bg-accent px-4 py-2 text-sm font-bold text-bg"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
