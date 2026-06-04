import type { ParsedSupportedMarket } from "./platforms";
import type { QueueStatus } from "./queue";

export type LifecycleState =
  | "no_market_detected"
  | "market_detected"
  | "api_snapshot_available"
  | "manual_snapshot_required"
  | "forecast_locked"
  | "forecast_queued"
  | "forecast_resolved";

export type LifecycleSummary = {
  state: LifecycleState;
  label: string;
};

export function lifecycleStateForMarket(
  market: ParsedSupportedMarket | null,
  status?: QueueStatus | "locked" | "resolved",
): LifecycleSummary {
  if (status === "locked" || status === "synced") {
    return { state: "forecast_locked", label: "Forecast locked" };
  }
  if (status === "pending" || status === "syncing" || status === "failed") {
    return { state: "forecast_queued", label: "Forecast queued" };
  }
  if (status === "resolved") {
    return { state: "forecast_resolved", label: "Forecast resolved" };
  }
  if (!market) {
    return { state: "no_market_detected", label: "No supported market detected" };
  }
  if (market.manualOnly) {
    return { state: "manual_snapshot_required", label: "Manual snapshot required" };
  }
  return { state: "api_snapshot_available", label: "Server API snapshot available" };
}
