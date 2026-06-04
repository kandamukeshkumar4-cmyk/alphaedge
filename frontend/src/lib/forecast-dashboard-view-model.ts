import type {
  BrierTrendPoint,
  ForecastDashboard,
  PlatformEdge,
  TimeBucketEdge,
} from "./forecast-mirror-api";

export type ForecastDashboardViewInput = ForecastDashboard;

export type SummaryCard = {
  label: string;
  value: string;
};

export type DashboardView = {
  emptyState: { title: string; body: string } | null;
  summaryCards: SummaryCard[];
  qualityLabels: string[];
  platformBreakdown: PlatformEdge[];
  timeBreakdown: TimeBucketEdge[];
  brierTrend: BrierTrendPoint[];
};

export function buildForecastDashboardView(
  dashboard: ForecastDashboardViewInput | null,
): DashboardView {
  if (!dashboard) {
    return {
      emptyState: {
        title: "No locked forecasts yet",
        body: "Lock research-only paper forecasts from the extension or web dashboard to start measuring skill.",
      },
      summaryCards: [
        { label: "Resolved", value: "0" },
        { label: "Open", value: "0" },
        { label: "Mean Brier", value: "N/A" },
        { label: "Synthetic PnL", value: "$0.00" },
      ],
      qualityLabels: [],
      platformBreakdown: [],
      timeBreakdown: [],
      brierTrend: [],
    };
  }

  const labels: string[] = [];
  if (dashboard.live.brier_provisional) {
    labels.push(`Brier provisional: ${dashboard.live.resolved_count}/30 resolved`);
  }
  if (dashboard.live.calibration_provisional) {
    labels.push(`Calibration provisional: ${dashboard.live.resolved_count}/150 resolved`);
  }
  const categoryRows = (dashboard.category_breakdown ?? []) as Array<{
    category: string;
    count: number;
    provisional?: boolean;
  }>;
  for (const category of categoryRows) {
    const provisional = category.provisional ?? (category.count > 0 && category.count < 20);
    if (provisional) {
      labels.push(`${category.category} category provisional: ${category.count}/20 resolved`);
    }
  }

  return {
    emptyState: dashboard.live.resolved_count + dashboard.live.unresolved_count === 0
      ? {
          title: "No locked forecasts yet",
          body: "Lock research-only paper forecasts from the extension or web dashboard to start measuring skill.",
        }
      : null,
    summaryCards: [
      { label: "Resolved", value: countLabel(dashboard.live.resolved_count) },
      { label: "Open", value: countLabel(dashboard.live.unresolved_count) },
      { label: "Mean Brier", value: scoreLabel(dashboard.live.mean_user_brier) },
      { label: "Synthetic PnL", value: moneyLabel(dashboard.live.synthetic_pnl_total) },
    ],
    qualityLabels: labels,
    platformBreakdown: dashboard.platform_breakdown ?? [],
    timeBreakdown: dashboard.time_breakdown ?? [],
    brierTrend: dashboard.brier_trend ?? [],
  };
}

function scoreLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return value.toFixed(4);
}

function countLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? "0" : value.toLocaleString();
}

function moneyLabel(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "$0.00";
  }
  return `$${value.toFixed(2)}`;
}
