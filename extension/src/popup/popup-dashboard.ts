import type { ForecastDashboardSummary, ForecastLifecycleSummary } from "../backend-client";
import type { QueuedForecast } from "../queue";

export type PopupDashboardView = {
  rollingBrier: string;
  independentCount: string;
  anchoredCount: string;
  pendingText: string;
  lastResolved: Array<{
    title: string;
    score: string;
    pnl: string;
  }>;
  empty: boolean;
};

export function buildPopupDashboardView(input: {
  dashboard: ForecastDashboardSummary | null;
  lifecycle: ForecastLifecycleSummary | null;
  queue: QueuedForecast[];
}): PopupDashboardView {
  const openQueue = input.queue.filter((row) => row.status !== "synced").length;
  const resolved = input.lifecycle?.recently_resolved ?? [];
  return {
    rollingBrier:
      input.dashboard?.live.mean_user_brier == null
        ? "No resolved forecasts"
        : input.dashboard.live.mean_user_brier.toFixed(3),
    independentCount: String(input.dashboard?.live.independent_count ?? 0),
    anchoredCount: String(input.dashboard?.live.anchored_count ?? 0),
    pendingText: `${openQueue} forecast${openQueue === 1 ? "" : "s"} pending`,
    lastResolved: resolved.slice(0, 5).map((row) => ({
      title: row.title,
      score: row.user_brier == null ? "pending score" : `Brier ${row.user_brier.toFixed(3)}`,
      pnl: row.synthetic_pnl == null ? "paper P&L pending" : `Paper P&L ${row.synthetic_pnl.toFixed(2)}`,
    })),
    empty: !input.dashboard && !resolved.length && openQueue === 0,
  };
}
