import type { NavIconKey } from "@/components/nav-icons";

/*
 * Loop V62 (R1) — the discoverability source of truth.
 *
 * Every shipped capability is listed here exactly once, grouped, labeled, with
 * a one-line "what it does" and a real deep link. The /features map page and
 * the grouped "More" nav both render from this list, so nothing can ship
 * without a visible, labeled surface (the 15-second rule). Routes are verified
 * to exist in src/app; embedded/overlay surfaces carry a `note` saying where
 * they actually live and deep-link to the page that hosts them.
 *
 * `badge: "NEW"` seeds the R3 NEW-badge registry — a UI hint only, never data.
 */

export type FeatureSurface = "page" | "overlay" | "embedded";

export interface FeatureEntry {
  id: string;
  label: string;
  /** Real, navigable route. Embedded/overlay entries link to their host page. */
  href: string;
  /** One-line, honest "what it does". No advice language, no fabricated metrics. */
  blurb: string;
  surface?: FeatureSurface;
  /** For embedded/overlay/admin surfaces: where the capability actually lives. */
  note?: string;
  /** Requires sign-in / admin auth. */
  requiresAuth?: boolean;
  badge?: "NEW";
}

export interface FeatureGroup {
  id: string;
  title: string;
  blurb: string;
  icon: NavIconKey;
  features: FeatureEntry[];
}

export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    id: "trade",
    title: "Markets & trading",
    blurb: "Browse markets and place simulated paper trades.",
    icon: "trade",
    features: [
      {
        id: "markets",
        label: "Markets",
        href: "/markets",
        blurb: "Browse every open market with live prices, candles and order books.",
      },
      {
        id: "trade",
        label: "Trade",
        href: "/trade",
        blurb: "Place simulated paper trades — no real money is ever used.",
      },
      {
        id: "opportunities",
        label: "Opportunities",
        href: "/opportunities",
        blurb: "The biggest model-vs-market edges right now.",
      },
      {
        id: "compare",
        label: "Compare",
        href: "/compare",
        blurb: "Put two markets side by side.",
      },
      {
        id: "arb",
        label: "Arb",
        href: "/arb",
        blurb: "Cross-venue matched pairs and dutching edges.",
      },
      {
        id: "market-context",
        label: "Market context panel",
        href: "/markets",
        surface: "embedded",
        note: "Shown inside each market — whales, venue gaps and news tone.",
        blurb: "Whale flow, venue gaps and news tone for the open market.",
      },
    ],
  },
  {
    id: "intel",
    title: "Intelligence & AI",
    blurb: "Model signals, forecasts and the AI analyst.",
    icon: "intel",
    features: [
      {
        id: "terminal",
        label: "Research Terminal",
        href: "/terminal",
        badge: "NEW",
        blurb:
          "Ask a market question — streamed research steps, confluence scoreboard, bull/bear case. Paper only.",
      },
      {
        id: "scanners",
        label: "Scanner Studio",
        href: "/scanners",
        badge: "NEW",
        blurb:
          "Describe a scanner in plain English — compiled spec, scheduled pipeline runs, paper alerts. Never orders.",
      },
      {
        id: "signals",
        label: "Signals",
        href: "/signals",
        blurb: "Model signals with unread alert badges.",
      },
      {
        id: "ai-analyze",
        label: "AI Analyze",
        href: "/markets",
        surface: "overlay",
        note: "Open the ✦ AI Analyze panel from any market.",
        blurb: "Ask the AI analyst about any market, with cited reasoning.",
      },
      {
        id: "research",
        label: "Research",
        href: "/research",
        blurb: "AI analyst briefs with citations.",
      },
      {
        id: "forecast",
        label: "Forecast",
        href: "/forecast",
        blurb: "Locked model forecasts per market.",
      },
      {
        id: "smart-money",
        label: "Smart money",
        href: "/smart-money",
        blurb: "Whale flow and position concentration.",
      },
      {
        id: "backtest",
        label: "Backtest",
        href: "/backtest",
        blurb: "Walk-forward CLV backtests.",
      },
      {
        id: "weather",
        label: "Weather",
        href: "/weather",
        blurb: "Weather edges for outdoor markets.",
      },
      {
        id: "macro",
        label: "Macro",
        href: "/macro",
        blurb: "Rates and macro context.",
      },
    ],
  },
  {
    id: "proof",
    title: "Proof & track record",
    blurb: "How the model actually performs — measured, not claimed.",
    icon: "proof",
    features: [
      {
        id: "eval",
        label: "Eval",
        href: "/eval",
        blurb: "Model-evaluation proof: cluster gate, composition and drift.",
      },
      {
        id: "track-record",
        label: "Track record",
        href: "/track-record",
        blurb: "Calibration and CLV over time.",
      },
      {
        id: "resolved",
        label: "Resolved",
        href: "/resolved",
        blurb: "Model calls versus real outcomes.",
      },
      {
        id: "pods",
        label: "Pods",
        href: "/pods",
        badge: "NEW",
        blurb: "Command center for the paper-trading pod fleet.",
      },
      {
        id: "heartbeat",
        label: "Heartbeat decisions",
        href: "/pods",
        surface: "embedded",
        badge: "NEW",
        note: "The live decision log runs inside Pods.",
        blurb: "The live decision log — every rule-gated pod action as it happens.",
      },
    ],
  },
  {
    id: "social",
    title: "People & social",
    blurb: "Traders, clones and the activity you follow.",
    icon: "social",
    features: [
      {
        id: "feed",
        label: "Feed",
        href: "/feed",
        blurb: "Activity stream from signals and the traders you follow.",
      },
      {
        id: "traders",
        label: "Traders & leaderboard",
        href: "/leaderboard",
        blurb: "Trader profiles, the leaderboard and following.",
      },
      {
        id: "clones",
        label: "Clones",
        href: "/clones",
        blurb: "Paper agent clones you can follow.",
      },
      {
        id: "alerts",
        label: "Alerts",
        href: "/alerts",
        blurb: "Price and signal triggers.",
      },
      {
        id: "notifications",
        label: "Notifications",
        href: "/alerts",
        surface: "overlay",
        note: "The bell in the header; full history lives in Alerts.",
        blurb: "The notifications bell — recent triggers at a glance.",
      },
      {
        id: "watchlist",
        label: "Watchlist",
        href: "/watchlist",
        blurb: "Markets you're tracking.",
      },
    ],
  },
  {
    id: "account",
    title: "Your account",
    blurb: "Your paper balance, positions and personal desk.",
    icon: "account",
    features: [
      {
        id: "portfolio",
        label: "Portfolio",
        href: "/portfolio",
        blurb: "Your paper balance, open positions and P&L.",
      },
      {
        id: "home",
        label: "Home",
        href: "/home",
        blurb: "Your personal desk home.",
      },
    ],
  },
  {
    id: "system",
    title: "System",
    blurb: "Health and operator tools.",
    icon: "system",
    features: [
      {
        id: "system-status",
        label: "System status",
        href: "/admin/observability",
        surface: "embedded",
        requiresAuth: true,
        note: "Live health shows in the header chip; full observability in Admin.",
        blurb: "API health and observability.",
      },
      {
        id: "admin",
        label: "Admin",
        href: "/admin",
        requiresAuth: true,
        blurb: "Calibration, resolution, proof and observability (sign-in required).",
      },
    ],
  },
];

/** Flat list of every registered feature — order preserved across groups. */
export const ALL_FEATURES: FeatureEntry[] = FEATURE_GROUPS.flatMap((g) => g.features);
