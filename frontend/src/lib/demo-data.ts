// Demo fixtures shown when the backend has no data (or is down) so every
// surface is explorable out of the box. Every consumer that renders these
// MUST show a "demo" chip — never present fixtures as live output.
import type { LeaderboardEntry } from "./leaderboard-api";
import type { SignalFeedItem } from "./signals-dashboard-api";
import type { AnalystBrief, TrackRecordRow } from "./polyscout-api";
import type { AlertItem, SignalEventItem } from "./activity-api";

const NOW = Date.now();
const iso = (minsAgo: number) => new Date(NOW - minsAgo * 60_000).toISOString();

export const DEMO_LEADERBOARD: LeaderboardEntry[] = [
  { rank: 1, username: "delta_scout", realized_pnl: 18432, total_trades: 212, win_rate: 0.61 },
  { rank: 2, username: "fadethecrowd", realized_pnl: 12780, total_trades: 145, win_rate: 0.58 },
  { rank: 3, username: "clv_hunter", realized_pnl: 9310, total_trades: 301, win_rate: 0.54 },
  { rank: 4, username: "night_owl", realized_pnl: 6205, total_trades: 98, win_rate: 0.55 },
  { rank: 5, username: "steamchaser", realized_pnl: 488, total_trades: 77, win_rate: 0.51 },
];

export const DEMO_SIGNALS: SignalFeedItem[] = [
  {
    id: "demo-sig-1", signal_type: "smart_money", platform: "polymarket",
    market_id: "wc26-final-winner", market_name: "World Cup 2026 Winner",
    implied_edge: 0.042, sample_size: 18, is_edge: true, provisional: false,
    created_at: iso(12), resolved: false,
  },
  {
    id: "demo-sig-2", signal_type: "arbitrage", platform: "kalshi",
    market_id: "fed-decision-july", market_name: "Fed decision in July?",
    implied_edge: 0.018, sample_size: 6, is_edge: true, provisional: true,
    created_at: iso(38), resolved: false,
  },
  {
    id: "demo-sig-3", signal_type: "forecast_edge", platform: "polymarket",
    market_id: "nba-2025-01-15-lal-bos", market_name: "Lakers vs Celtics",
    implied_edge: 0.031, sample_size: 42, is_edge: true, provisional: false,
    created_at: iso(65), resolved: false,
  },
  {
    id: "demo-sig-4", signal_type: "dutching", platform: "kalshi",
    market_id: "next-leader-poll", market_name: "Next leader out of power?",
    implied_edge: null, sample_size: 3, is_edge: false, provisional: true,
    created_at: iso(120), resolved: false,
  },
];

export const DEMO_BRIEFS: AnalystBrief[] = [
  {
    id: "demo-brief-1", market_slug: "wc26-final-winner", kind: "brief",
    headline: "Whale accumulation meets unpriced squad news on WC26 favorite",
    body_markdown:
      "Three qualified wallets added a combined $410k YES over 40 minutes while the book barely moved. A starting-XI report from 22 minutes ago has not repriced the market. Model edge sits at +3.1 points vs the mid.",
    citations: [
      { kind: "whale_delta", label: "3 wallets +$410k YES in 40m" },
      { kind: "news_arrival", label: "Squad news, relevance 0.72, unpriced" },
      { kind: "price_jump", label: "Mid +80bps on rising volume" },
      { kind: "model", label: "Model 58% vs market 55%" },
    ],
    generator: "fallback", model_version: "xgb-14", prompt_version: "v1",
    latency_ms: 412, created_at: iso(25),
    claim: {
      id: "demo-claim-1", market_slug: "wc26-final-winner", direction: "up",
      horizon_minutes: 240, confidence: 0.64, price_at_claim: 0.55,
      status: "pending", resolution_price: null, resolved_at: null, created_at: iso(25),
    },
  },
  {
    id: "demo-brief-2", market_slug: "fed-decision-july", kind: "brief",
    headline: "Order-book flip on rate market after CPI whisper numbers",
    body_markdown:
      "Bid depth flipped 2.3:1 to YES within one window while spread held. No qualifying whale prints; treating as retail steam until confirmed.",
    citations: [
      { kind: "orderbook_flip", label: "Depth ratio 2.3:1 to YES" },
      { kind: "news_arrival", label: "CPI whisper thread, relevance 0.55" },
      { kind: "model", label: "Model 88% vs market 90%" },
    ],
    generator: "fallback", model_version: "xgb-14", prompt_version: "v1",
    latency_ms: 388, created_at: iso(95),
    claim: {
      id: "demo-claim-2", market_slug: "fed-decision-july", direction: "down",
      horizon_minutes: 120, confidence: 0.55, price_at_claim: 0.9,
      status: "correct", resolution_price: 0.87, resolved_at: iso(30), created_at: iso(95),
    },
  },
  {
    id: "demo-brief-3", market_slug: "nba-2025-01-15-lal-bos", kind: "digest",
    headline: "Morning research: 10 movers, 2 alignment triggers, 1 graded win",
    body_markdown:
      "Top movers ranked by 24h repricing. Two markets crossed the 3-layer alignment bar overnight; claim #2 resolved correct (+3 points inside horizon).",
    citations: [{ kind: "digest", label: "Daily scoreboard" }],
    generator: "fallback", model_version: "xgb-14", prompt_version: "v1",
    latency_ms: 902, created_at: iso(360), claim: null,
  },
];

export const DEMO_TRACK_RECORD: TrackRecordRow[] = [
  { dimension: "window", dim_key: "all", window_days: 30, n: 47, accuracy: 0.62, brier: 0.214, provisional: false },
];

export const DEMO_ALERTS: AlertItem[] = [
  {
    id: "demo-alert-1", alert_type: "alignment",
    message: "3 layers aligned on World Cup 2026 Winner — analyst dispatched",
    payload: { market: "wc26-final-winner" }, acknowledged: false, created_at: iso(26),
  },
  {
    id: "demo-alert-2", alert_type: "brief",
    message: "New brief published: order-book flip on Fed decision market",
    payload: { market: "fed-decision-july" }, acknowledged: false, created_at: iso(94),
  },
];

export const DEMO_EVENTS: SignalEventItem[] = [
  {
    id: "demo-ev-1", signal_type: "whale_delta", platform: "polymarket",
    market_id: "wc26-final-winner", headline_eligible: true,
    payload: { wallets: 3, notional: 410000 }, created_at: iso(28),
  },
  {
    id: "demo-ev-2", signal_type: "news_arrival", platform: "polymarket",
    market_id: "wc26-final-winner", headline_eligible: true,
    payload: { relevance: 0.72 }, created_at: iso(35),
  },
  {
    id: "demo-ev-3", signal_type: "price_jump", platform: "kalshi",
    market_id: "fed-decision-july", headline_eligible: false,
    payload: { move_bps: 110 }, created_at: iso(96),
  },
  {
    id: "demo-ev-4", signal_type: "volume_surge", platform: "polymarket",
    market_id: "nba-2025-01-15-lal-bos", headline_eligible: false,
    payload: { volume_usd: 62000 }, created_at: iso(150),
  },
];

// Small badge component data — consumers render this label text.
export const DEMO_LABEL = "demo";
