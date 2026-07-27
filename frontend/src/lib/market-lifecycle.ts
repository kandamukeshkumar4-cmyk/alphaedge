import type { Market } from "./mock-data";

export type MarketLifecycle = "live" | "closed" | "decided";

/**
 * Derive the honest display lifecycle from fields the market API already owns.
 * Status is authoritative. Exact endpoint prices are a defensive fallback; a
 * small, genuinely open probability must never be promoted to "decided" just
 * because the UI rounds it to 0% or 100%.
 */
export function marketLifecycle(
  market: Pick<Market, "status" | "endsAt" | "outcomes">,
  nowMs = Date.now(),
): MarketLifecycle {
  if (market.status === "resolved") return "decided";
  if (market.status === "locked") return "closed";

  const yesPrice = market.outcomes[0]?.price;
  if (typeof yesPrice === "number" && Number.isFinite(yesPrice)) {
    if (yesPrice <= 0 || yesPrice >= 1) return "decided";
  }

  const closeMs = Date.parse(market.endsAt);
  if (!Number.isNaN(closeMs) && closeMs <= nowMs) return "closed";

  return "live";
}

export function marketLifecycleLabel(lifecycle: MarketLifecycle): "LIVE" | "Closed" | "Decided" {
  if (lifecycle === "decided") return "Decided";
  if (lifecycle === "closed") return "Closed";
  return "LIVE";
}

/** Return an honest, current countdown only for a live market with a valid future close. */
export function marketCloseCountdown(
  lifecycle: MarketLifecycle | null,
  endsAt: string,
  nowMs = Date.now(),
): string | null {
  if (lifecycle !== "live") return null;

  const closeMs = Date.parse(endsAt);
  if (!Number.isFinite(closeMs) || closeMs <= nowMs) return null;

  const remainingMs = closeMs - nowMs;
  const hours = Math.floor(remainingMs / 3_600_000);
  const minutes = Math.floor((remainingMs % 3_600_000) / 60_000);
  if (hours >= 48) return `${Math.floor(hours / 24)}d`;
  if (hours >= 1) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

type DetailLifecycleEvidence = {
  status: Market["status"];
  // Loop117 (D5): a detail payload may carry an honest null price when the
  // market has no stored quote — the guard below already ignores non-numbers.
  outcomes: Array<{ label: string; price: number | null }>;
};

/**
 * Detail payloads carry authoritative status/prices but not lock_at. Until a
 * catalog row supplies the real close time, do not reuse a bundled mock date.
 */
export function marketLifecycleFromDetail(
  market: Market,
  detail: DetailLifecycleEvidence | null,
  catalogEndsAt: string | null | undefined,
  nowMs = Date.now(),
): MarketLifecycle {
  if (!detail) return marketLifecycle(market, nowMs);

  const yesPrice = detail.outcomes.find((outcome) => outcome.label.toUpperCase() === "YES")?.price;
  const outcomes =
    typeof yesPrice === "number" && Number.isFinite(yesPrice)
      ? market.outcomes.map((outcome, index) =>
          index === 0 ? { ...outcome, price: yesPrice } : outcome,
        )
      : market.outcomes;

  return marketLifecycle(
    {
      ...market,
      status: detail.status,
      endsAt: catalogEndsAt ?? "",
      outcomes,
    },
    nowMs,
  );
}
