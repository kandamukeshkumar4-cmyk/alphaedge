"use client";

import { FormEvent, useEffect, useState } from "react";

import { API_BASE } from "@/lib/alphaedge-api";
import { useAdminApiKey } from "@/lib/admin-context";
const API = API_BASE;

const CATALOG_SLUGS = [
  "nba-2025-01-15-lal-bos",
  "elect-la-mayor-2026",
  "wc2026-m1-mex-homewin",
  "wc2026-m1-draw",
  "wc2026-m1-rsa-awaywin",
  "wc2026-winner-brazil",
  "wc2026-winner-france",
  "wc2026-winner-argentina",
] as const;

type CalibrationGate = "pass" | "fail" | "no-data";

type CalibrationLatest = {
  brier_score: number | null;
  calibration_error: number | null;
  markets_evaluated: number;
  last_updated: string;
  gate: CalibrationGate;
  paper_trading_only: boolean;
};

function brierMeterColor(score: number | null): string {
  if (score === null) {
    return "#64748b";
  }
  if (score < 0.2) {
    return "#22c55e";
  }
  if (score <= 0.25) {
    return "#eab308";
  }
  return "#ef4444";
}

function gateBadgeStyle(gate: CalibrationGate): { background: string; color: string; border: string } {
  if (gate === "pass") {
    return { background: "rgba(34, 197, 94, 0.12)", color: "#22c55e", border: "1px solid rgba(34, 197, 94, 0.35)" };
  }
  if (gate === "fail") {
    return { background: "rgba(239, 68, 68, 0.12)", color: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.35)" };
  }
  return { background: "rgba(100, 116, 139, 0.12)", color: "#94a3b8", border: "1px solid rgba(100, 116, 139, 0.35)" };
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function CalibrationAdminPage() {
  const [data, setData] = useState<CalibrationLatest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolveSlug, setResolveSlug] = useState<string>(CATALOG_SLUGS[0]);
  const [resolveOutcome, setResolveOutcome] = useState<"YES" | "NO" | "VOID">("YES");
  const adminApiKey = useAdminApiKey();
  const [resolveMessage, setResolveMessage] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [resolveLoading, setResolveLoading] = useState(false);

  useEffect(() => {
    if (!API) {
      setLoading(false);
      setError("Set NEXT_PUBLIC_API_URL to load calibration metrics.");
      return;
    }

    fetch(`${API}/api/v1/calibration/latest`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Request failed (${response.status})`);
        }
        return response.json() as Promise<CalibrationLatest>;
      })
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch(() => {
        setData(null);
        setError("Could not load calibration metrics from the API.");
      })
      .finally(() => setLoading(false));
  }, []);

  const meterPercent =
    data?.brier_score !== null && data?.brier_score !== undefined
      ? Math.min(100, Math.max(0, (data.brier_score / 0.5) * 100))
      : 0;
  const gateStyle = gateBadgeStyle(data?.gate ?? "no-data");

  async function handleResolveMarket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResolveMessage(null);
    setResolveError(null);

    if (!API) {
      setResolveError("Set NEXT_PUBLIC_API_URL to resolve markets.");
      return;
    }
    if (!adminApiKey.trim()) {
      setResolveError("Admin API key is required.");
      return;
    }

    setResolveLoading(true);
    try {
      const response = await fetch(`${API}/api/v1/admin/markets/${resolveSlug}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-API-Key": adminApiKey.trim(),
        },
        body: JSON.stringify({ winning_outcome: resolveOutcome }),
      });

      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
        paper_orders_settled?: number;
      };

      if (!response.ok) {
        setResolveError(body.detail ?? `Request failed (${response.status})`);
        return;
      }

      setResolveMessage(
        `Resolved ${resolveSlug} as ${resolveOutcome}. Settled ${body.paper_orders_settled ?? 0} paper order(s).`,
      );
    } catch {
      setResolveError("Could not reach the API to resolve this market.");
    } finally {
      setResolveLoading(false);
    }
  }

  return (
    <main
      style={{
        margin: "0 auto",
        maxWidth: "56rem",
        padding: "2rem 1.5rem",
        fontFamily: "system-ui, sans-serif",
        color: "#e2e8f0",
      }}
    >
      <header style={{ marginBottom: "1.5rem", borderBottom: "1px solid #1e293b", paddingBottom: "1rem" }}>
        <p style={{ margin: 0, fontSize: "0.75rem", letterSpacing: "0.12em", textTransform: "uppercase", color: "#38bdf8" }}>
          Admin
        </p>
        <h1 style={{ margin: "0.5rem 0 0", fontSize: "1.875rem", fontWeight: 600 }}>Calibration</h1>
        <p style={{ margin: "0.5rem 0 0", fontSize: "0.875rem", color: "#94a3b8" }}>
          Paper-trading forecast calibration gate (Brier &lt; 0.25)
        </p>
      </header>

      {loading ? <p style={{ color: "#94a3b8" }}>Loading calibration metrics…</p> : null}
      {error ? <p style={{ color: "#fbbf24" }}>{error}</p> : null}

      {data ? (
        <section style={{ display: "grid", gap: "1rem" }}>
          {data.gate === "no-data" ? (
            <div
              style={{
                borderRadius: "0.75rem",
                border: "1px solid #334155",
                background: "#0f172a",
                padding: "1rem",
                color: "#cbd5e1",
              }}
            >
              No resolved paper markets yet. Calibration metrics will appear after markets settle.
            </div>
          ) : null}

          <div
            style={{
              borderRadius: "0.75rem",
              border: "1px solid #1e293b",
              background: "#0b1220",
              padding: "1.25rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
              <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Brier Score</h2>
              <span
                style={{
                  display: "inline-flex",
                  borderRadius: "999px",
                  padding: "0.25rem 0.75rem",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  ...gateStyle,
                }}
              >
                {data.gate}
              </span>
            </div>

            <p style={{ margin: "0.75rem 0 0", fontSize: "2rem", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
              {data.brier_score !== null ? data.brier_score.toFixed(4) : "—"}
            </p>

            <div
              aria-hidden
              style={{
                marginTop: "1rem",
                height: "0.75rem",
                borderRadius: "999px",
                background: "#1e293b",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${meterPercent}%`,
                  height: "100%",
                  background: brierMeterColor(data.brier_score),
                  transition: "width 0.3s ease",
                }}
              />
            </div>
            <p style={{ margin: "0.5rem 0 0", fontSize: "0.75rem", color: "#64748b" }}>
              Green &lt; 0.20 · Yellow 0.20–0.25 · Red &gt; 0.25
            </p>
          </div>

          <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <MetricCard label="Markets evaluated" value={String(data.markets_evaluated)} />
            <MetricCard
              label="Calibration error"
              value={data.calibration_error !== null ? data.calibration_error.toFixed(4) : "—"}
            />
            <MetricCard label="Last updated" value={formatTimestamp(data.last_updated)} />
            <MetricCard label="Paper only" value={data.paper_trading_only ? "Yes" : "No"} />
          </div>
        </section>
      ) : null}

      <section style={{ marginTop: "1rem" }}>
        <div
          style={{
            borderRadius: "0.75rem",
            border: "1px solid #1e293b",
            background: "#0b1220",
            padding: "1.25rem",
          }}
        >
          <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>Resolve Market</h2>
          <p style={{ margin: "0.5rem 0 0", fontSize: "0.875rem", color: "#94a3b8" }}>
            Settle paper positions for a catalog market (admin only).
          </p>

          <form onSubmit={(event) => void handleResolveMarket(event)} style={{ marginTop: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.75rem", color: "#64748b" }}>
              Market
              <select
                value={resolveSlug}
                onChange={(event) => setResolveSlug(event.target.value)}
                style={{
                  display: "block",
                  marginTop: "0.35rem",
                  width: "100%",
                  borderRadius: "0.5rem",
                  border: "1px solid #334155",
                  background: "#0f172a",
                  color: "#e2e8f0",
                  padding: "0.5rem 0.75rem",
                }}
              >
                {CATALOG_SLUGS.map((slug) => (
                  <option key={slug} value={slug}>
                    {slug}
                  </option>
                ))}
              </select>
            </label>

            <fieldset style={{ marginTop: "1rem", border: "none", padding: 0 }}>
              <legend style={{ fontSize: "0.75rem", color: "#64748b" }}>Winning outcome</legend>
              <label style={{ marginRight: "1rem", fontSize: "0.875rem" }}>
                <input
                  type="radio"
                  name="resolve-outcome"
                  value="YES"
                  checked={resolveOutcome === "YES"}
                  onChange={() => setResolveOutcome("YES")}
                />{" "}
                YES
              </label>
              <label style={{ fontSize: "0.875rem" }}>
                <input
                  type="radio"
                  name="resolve-outcome"
                  value="NO"
                  checked={resolveOutcome === "NO"}
                  onChange={() => setResolveOutcome("NO")}
                />{" "}
                NO
              </label>
            </fieldset>

            <button
              type="submit"
              disabled={resolveLoading}
              style={{
                marginTop: "1rem",
                borderRadius: "0.5rem",
                border: "1px solid #38bdf8",
                background: "#0ea5e9",
                color: "#0f172a",
                fontWeight: 700,
                padding: "0.5rem 1rem",
                cursor: resolveLoading ? "not-allowed" : "pointer",
                opacity: resolveLoading ? 0.6 : 1,
              }}
            >
              {resolveLoading ? "Resolving…" : "Resolve market"}
            </button>
          </form>

          {resolveMessage ? (
            <p style={{ marginTop: "1rem", fontSize: "0.875rem", color: "#22c55e" }}>{resolveMessage}</p>
          ) : null}
          {resolveError ? (
            <p style={{ marginTop: "1rem", fontSize: "0.875rem", color: "#fbbf24" }}>{resolveError}</p>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        borderRadius: "0.75rem",
        border: "1px solid #1e293b",
        background: "#0f172a",
        padding: "1rem",
      }}
    >
      <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "#64748b" }}>
        {label}
      </div>
      <div style={{ marginTop: "0.5rem", fontSize: "1.125rem", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
    </div>
  );
}
