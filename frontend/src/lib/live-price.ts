/** Shared live-price helpers for mirror markets (Kalshi / Polymarket). */

export function wsBase(): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (configured) {
    return configured.replace(/^http/, "ws").replace(/\/$/, "");
  }
  const api = process.env.NEXT_PUBLIC_API_URL;
  if (api) {
    return api.replace(/^http/, "ws").replace(/\/$/, "");
  }
  return "ws://localhost:8000";
}

export function resolveOutcomeSlug(outcomeId: string, marketSlug: string): string {
  if (outcomeId.startsWith("pm-") || outcomeId.startsWith("ks-")) {
    return outcomeId;
  }
  return marketSlug;
}

export function payoutMultiplier(probability: number): string {
  if (probability <= 0.01) return "—";
  return `${(1 / probability).toFixed(2)}x`;
}

export function formatVolUsd(volume: number): string {
  if (volume >= 1_000_000) {
    return `$${(volume / 1_000_000).toFixed(volume >= 10_000_000 ? 1 : 2)}M`;
  }
  if (volume >= 1_000) {
    return `$${Math.round(volume / 1_000)}K`;
  }
  return `$${volume.toLocaleString()}`;
}
