/** Shared live-price helpers for mirror markets (Kalshi / Polymarket). */
import { WS_BASE } from "./alphaedge-api";

export function wsBase(): string {
  // Reuse the single resolved backend so the socket and REST never diverge —
  // an empty base would silently point the WS at the static host and hang.
  return WS_BASE.replace(/\/$/, "");
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
