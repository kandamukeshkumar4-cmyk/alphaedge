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

type DetailLifecycleEvidence = {
  status: Market["status"];
  outcomes: Array<{ label: string; price: number }>;
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
