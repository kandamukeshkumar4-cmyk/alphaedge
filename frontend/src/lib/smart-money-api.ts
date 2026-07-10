import { API_BASE, apiUrl, ensureApiBase, hasLiveApi } from "@/lib/alphaedge-api";

/**
 * Per-market smart-money aggregate — GET /api/v1/smart-money?slug=&hours=&top_n=
 * (backend G07). READ-ONLY analysis: signal_only is always true, no order path.
 * Wallet addresses arrive pre-truncated ("0xwhaleA…"). See API-NOTES.md → G07.
 */
export type TopHolders = {
  wallet_count: number;
  top_n: number;
  top_share: number;
  total_size: number;
  error: string | null;
};

export type WhaleDelta = {
  wallet: string;
  action: string;
  outcome: string;
  direction: string;
  size_change: number;
};

export type RecentLargeFlows = {
  whale_count: number;
  deltas: WhaleDelta[];
  error: string | null;
};

export type DepthSkew = {
  bid_size: number;
  ask_size: number;
  skew: number;
  levels: number;
  error: string | null;
};

export type TradeIntensity = {
  fill_count: number;
  notional: number;
  fills_per_hour: number;
  error: string | null;
};

export type SmartMoney = {
  slug: string;
  hours: number;
  market_found: boolean;
  paper_trading_only: boolean;
  signal_only: boolean;
  disclaimer: string;
  top_holders: TopHolders;
  recent_large_flows: RecentLargeFlows;
  depth_skew: DepthSkew;
  trade_intensity: TradeIntensity;
  generated_at: string;
};

export type FlowRowView = {
  wallet: string;
  action: string;
  outcome: string;
  direction: string;
  sizeLabel: string;
  isBuy: boolean;
};

export type SmartMoneyView = {
  found: boolean;
  slug: string;
  hoursLabel: string;
  concentrationLabel: string;
  walletCountLabel: string;
  totalSizeLabel: string;
  /** 0..1 magnitude for the concentration gauge. */
  concentrationRatio: number;
  depthSkewLabel: string;
  depthSkewTone: "up" | "down" | "neutral";
  fillsPerHourLabel: string;
  fillCountLabel: string;
  notionalLabel: string;
  /** 0..1 magnitude for the intensity bar (relative to INTENSITY_REF). */
  intensityRatio: number;
  flows: FlowRowView[];
  hasFlows: boolean;
  errors: string[];
  disclaimer: string;
};

// A single G07 call returns one trade-intensity aggregate, not a time series,
// so a real per-bucket sparkline is not available from the contract. We render
// a magnitude bar instead (noted in the loop log). This reference caps it.
export const INTENSITY_REF = 20;

function num(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

function moneyCompact(value: number): string {
  const v = num(value);
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

function sizeCompact(value: number): string {
  const v = num(value);
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toFixed(0);
}

/** Pure transform: raw G07 response → view model. Honest when market_found=false. */
export function buildSmartMoneyView(raw: SmartMoney | null): SmartMoneyView {
  const disclaimer =
    raw?.disclaimer ??
    "Research signal only — aggregated whale/flow observations, not advice. Paper trading only; simulated funds, no execution.";

  if (!raw || !raw.market_found) {
    return {
      found: false,
      slug: raw?.slug ?? "",
      hoursLabel: raw ? `${raw.hours}h` : "24h",
      concentrationLabel: "—",
      walletCountLabel: "0",
      totalSizeLabel: "—",
      concentrationRatio: 0,
      depthSkewLabel: "—",
      depthSkewTone: "neutral",
      fillsPerHourLabel: "—",
      fillCountLabel: "0",
      notionalLabel: "—",
      intensityRatio: 0,
      flows: [],
      hasFlows: false,
      errors: [],
      disclaimer,
    };
  }

  const th = raw.top_holders;
  const flows = raw.recent_large_flows;
  const skew = raw.depth_skew;
  const ti = raw.trade_intensity;

  const errors = [th.error, flows.error, skew.error, ti.error].filter(
    (e): e is string => typeof e === "string" && e.length > 0,
  );

  const skewValue = num(skew.skew);
  const flowRows: FlowRowView[] = (flows.deltas ?? []).map((d) => {
    const dir = (d.direction ?? "").toLowerCase();
    return {
      wallet: d.wallet,
      action: d.action,
      outcome: d.outcome,
      direction: d.direction,
      sizeLabel: sizeCompact(d.size_change),
      isBuy: dir === "buy" || dir === "add",
    };
  });

  return {
    found: true,
    slug: raw.slug,
    hoursLabel: `${raw.hours}h`,
    concentrationLabel: `${(num(th.top_share) * 100).toFixed(1)}%`,
    walletCountLabel: String(th.wallet_count ?? 0),
    totalSizeLabel: sizeCompact(th.total_size),
    concentrationRatio: Math.max(0, Math.min(1, num(th.top_share))),
    depthSkewLabel: `${skewValue > 0 ? "+" : ""}${skewValue.toFixed(2)}`,
    depthSkewTone: skewValue > 0.05 ? "up" : skewValue < -0.05 ? "down" : "neutral",
    fillsPerHourLabel: num(ti.fills_per_hour).toFixed(1),
    fillCountLabel: String(ti.fill_count ?? 0),
    notionalLabel: moneyCompact(ti.notional),
    intensityRatio: Math.max(0, Math.min(1, num(ti.fills_per_hour) / INTENSITY_REF)),
    flows: flowRows,
    hasFlows: flowRows.length > 0,
    errors,
    disclaimer,
  };
}

/** Fetch per-market smart money. Returns null with no live API or on error. */
export async function fetchSmartMoney(
  slug: string,
  opts?: { hours?: number; topN?: number; signal?: AbortSignal },
): Promise<SmartMoney | null> {
  const trimmed = slug.trim();
  if (!trimmed) return null;
  const base = (await ensureApiBase()) || API_BASE;
  if (!hasLiveApi(base)) return null;
  const params = new URLSearchParams({ slug: trimmed });
  if (opts?.hours) params.set("hours", String(opts.hours));
  if (opts?.topN) params.set("top_n", String(opts.topN));
  try {
    const res = await fetch(`${apiUrl("/api/v1/smart-money", base)}?${params.toString()}`, {
      cache: "no-store",
      signal: opts?.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as SmartMoney;
  } catch {
    return null;
  }
}
