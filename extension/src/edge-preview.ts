export type TimeToCloseBucket = "7d+" | "1-7d" | "6-24h" | "1-6h" | "<1h" | "unknown";

export type EdgePreview = {
  delta: number | null;
  deltaLabel: string;
  anchored: boolean;
  anchoringLabel: string;
  timeBucket: TimeToCloseBucket;
  timeLabel: string;
  paperPnlLabel: string;
};

const ANCHOR_EPSILON = 0.02;
const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

export function buildEdgePreview(input: {
  userProbability: number;
  marketImpliedProbability: number | null;
  closeAt?: string;
  now?: Date;
}): EdgePreview {
  const now = input.now ?? new Date();
  const timeBucket = timeToCloseBucket(input.closeAt, now);
  const timeLabel = timeToCloseLabel(input.closeAt, now);

  if (input.marketImpliedProbability === null) {
    return {
      delta: null,
      deltaLabel: "Market-implied probability unavailable before lock.",
      anchored: false,
      anchoringLabel: "Server snapshot is used when allowed; this remains research and paper simulation only.",
      timeBucket,
      timeLabel,
      paperPnlLabel: "Paper 1-unit frame appears after a market-implied probability is available.",
    };
  }

  const delta = round(input.userProbability - input.marketImpliedProbability);
  const anchored = Math.abs(delta) <= ANCHOR_EPSILON;
  const deltaLabel = `${delta >= 0 ? "+" : ""}${formatPct(delta)} vs market implied`;
  return {
    delta,
    deltaLabel,
    anchored,
    anchoringLabel: anchored
      ? "Anchored: counts for participation, not independent edge."
      : "Independent edge candidate for post-resolution scoring.",
    timeBucket,
    timeLabel,
    paperPnlLabel: paperPnlFrame(input.userProbability, input.marketImpliedProbability, anchored),
  };
}

export function timeToCloseBucket(closeAt: string | undefined, now = new Date()): TimeToCloseBucket {
  const diff = millisecondsUntil(closeAt, now);
  if (diff === null) {
    return "unknown";
  }
  if (diff >= 7 * DAY_MS) {
    return "7d+";
  }
  if (diff >= DAY_MS) {
    return "1-7d";
  }
  if (diff >= 6 * HOUR_MS) {
    return "6-24h";
  }
  if (diff >= HOUR_MS) {
    return "1-6h";
  }
  return "<1h";
}

export function timeToCloseLabel(closeAt: string | undefined, now = new Date()): string {
  const diff = millisecondsUntil(closeAt, now);
  if (diff === null) {
    return "Close time unknown";
  }
  if (diff <= 0) {
    return "Close time reached";
  }
  const hours = Math.floor(diff / HOUR_MS);
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  if (days > 0) {
    return `Closes in ${days}d ${remainingHours}h`;
  }
  const minutes = Math.max(1, Math.floor((diff % HOUR_MS) / (60 * 1000)));
  return `Closes in ${hours}h ${minutes}m`;
}

export function shouldPromptForReforecast(bucket: TimeToCloseBucket): boolean {
  return bucket === "1-6h" || bucket === "<1h";
}

function paperPnlFrame(
  userProbability: number,
  marketImpliedProbability: number,
  anchored: boolean,
): string {
  if (anchored) {
    return "Paper 1-unit frame: anchored forecasts carry no independent P&L signal.";
  }
  if (userProbability > marketImpliedProbability) {
    return `Paper 1-unit frame: YES-side score at ${formatPct(marketImpliedProbability)} implied.`;
  }
  return `Paper 1-unit frame: NO-side score from ${formatPct(marketImpliedProbability)} YES implied.`;
}

function millisecondsUntil(closeAt: string | undefined, now: Date): number | null {
  if (!closeAt) {
    return null;
  }
  const timestamp = Date.parse(closeAt);
  if (!Number.isFinite(timestamp)) {
    return null;
  }
  return timestamp - now.getTime();
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)} pts`;
}

function round(value: number): number {
  return Math.round(value * 10_000) / 10_000;
}
