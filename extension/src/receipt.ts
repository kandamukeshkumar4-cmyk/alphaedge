import type { LockForecastMessage } from "./messaging";
import type { SupportedProvider } from "./platforms";
import type { QueueStatus } from "./queue";

export type ForecastReceiptInput = {
  message: LockForecastMessage;
  lockedAt: string;
  platform: SupportedProvider;
  status: QueueStatus | "locked" | "queued";
};

export function buildForecastReceipt(input: ForecastReceiptInput): string {
  const payload = input.message.payload;
  return [
    "AlphaEdge Mirror forecast receipt",
    `Locked at: ${input.lockedAt}`,
    `Platform: ${input.platform}`,
    `Market: ${payload.market_title || payload.url}`,
    `Outcome: ${payload.outcome_label}`,
    `User probability: ${formatPercent(payload.user_probability)}`,
    `Implied probability: ${formatImplied(payload.market_implied_probability)}`,
    `Status: ${input.status}`,
    "Research and paper simulation only.",
  ].join("\n");
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatImplied(value: number | null): string {
  if (value === null) {
    return "server snapshot";
  }
  return formatPercent(value);
}
