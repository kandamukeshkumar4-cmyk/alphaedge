import type { Metadata } from "next";

import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";

/** Public site origin for absolute OG/canonical URLs (custom domain is owner action). */
export const SITE_URL =
  (process.env.NEXT_PUBLIC_SITE_URL || "").trim().replace(/\/+$/, "") ||
  "https://alphaedge-frontend-three.vercel.app";

export const SITE_NAME = "AlphaEdge";

export const DEFAULT_TITLE = "AlphaEdge — AI Prediction Markets";

export const DEFAULT_DESCRIPTION = PAPER_TRADING_DISCLAIMER;

/** Public routes listed in sitemap / robots allowlist. Admin is intentionally excluded. */
export const PUBLIC_SITEMAP_ROUTES: ReadonlyArray<{
  path: string;
  title: string;
  description: string;
  changeFrequency?: "always" | "hourly" | "daily" | "weekly" | "monthly" | "yearly" | "never";
  priority?: number;
}> = [
  {
    path: "/",
    title: "Discover",
    description:
      "Paper-trading prediction markets for sports and elections — explore edges, lock forecasts, prove the call.",
    changeFrequency: "hourly",
    priority: 1,
  },
  {
    path: "/about",
    title: "About",
    description:
      "What AlphaEdge is: a paper-trading prediction research platform with simulated funds and public proof.",
    changeFrequency: "monthly",
    priority: 0.7,
  },
  {
    path: "/terms",
    title: "Terms & disclaimer",
    description:
      "Paper-trading terms and disclaimer. Simulated funds only; not financial advice; no real-money execution.",
    changeFrequency: "monthly",
    priority: 0.5,
  },
  {
    path: "/features",
    title: "Features",
    description:
      "Full map of AlphaEdge capabilities: markets, AI analysis, proof dashboards, pods, and more.",
    changeFrequency: "weekly",
    priority: 0.8,
  },
  {
    path: "/markets",
    title: "Markets",
    description:
      "Browse open paper markets across sports and elections. Simulated funds only.",
    changeFrequency: "hourly",
    priority: 0.9,
  },
  {
    path: "/trade",
    title: "Trade",
    description:
      "Paper trade prediction markets with simulated funds. Research and portfolio demonstration only.",
    changeFrequency: "daily",
    priority: 0.85,
  },
  {
    path: "/signals",
    title: "Signals",
    description:
      "Model-vs-market signal desk for paper research. No real-money execution.",
    changeFrequency: "hourly",
    priority: 0.8,
  },
  {
    path: "/portfolio",
    title: "Portfolio",
    description:
      "Simulated portfolio, positions, and paper P&L. Research demonstration only.",
    changeFrequency: "daily",
    priority: 0.8,
  },
  {
    path: "/eval",
    title: "Proof",
    description:
      "Live evaluation and calibration proof — Brier, model registry, and honest unmeasured states.",
    changeFrequency: "daily",
    priority: 0.9,
  },
  {
    path: "/leaderboard",
    title: "Leaderboard",
    description:
      "Paper-trading leaderboard of simulated portfolio performance.",
    changeFrequency: "daily",
    priority: 0.7,
  },
  {
    path: "/pods",
    title: "Pods",
    description:
      "Research pods with paper equity and decision logs. Simulated funds only.",
    changeFrequency: "daily",
    priority: 0.75,
  },
  {
    path: "/research",
    title: "Research",
    description:
      "Desk research briefs and market intelligence. Paper trading only.",
    changeFrequency: "daily",
    priority: 0.7,
  },
  {
    path: "/forecast",
    title: "Forecast",
    description:
      "Locked model forecasts and scoring overview. Not financial advice.",
    changeFrequency: "daily",
    priority: 0.7,
  },
  {
    path: "/track-record",
    title: "Track record",
    description:
      "Historical paper track record and reliability views from resolved markets.",
    changeFrequency: "weekly",
    priority: 0.65,
  },
  {
    path: "/backtest",
    title: "Backtest",
    description:
      "Walk-forward paper backtests with Brier and flat-stake research metrics.",
    changeFrequency: "weekly",
    priority: 0.65,
  },
  {
    path: "/opportunities",
    title: "Opportunities",
    description:
      "Model-vs-market opportunity board for paper research.",
    changeFrequency: "hourly",
    priority: 0.7,
  },
  {
    path: "/watchlist",
    title: "Watchlist",
    description: "Personal market watchlist for paper trading research.",
    changeFrequency: "weekly",
    priority: 0.5,
  },
  {
    path: "/compare",
    title: "Compare",
    description: "Side-by-side market intelligence comparison. Paper trading only.",
    changeFrequency: "weekly",
    priority: 0.55,
  },
  {
    path: "/clones",
    title: "Clones",
    description: "Clone research strategies as paper portfolios.",
    changeFrequency: "weekly",
    priority: 0.55,
  },
  {
    path: "/feed",
    title: "Feed",
    description: "Activity and signal feed for the paper-trading desk.",
    changeFrequency: "hourly",
    priority: 0.6,
  },
  {
    path: "/discover",
    title: "Discover",
    description: "Discover paper markets and signals. Simulated funds only.",
    changeFrequency: "hourly",
    priority: 0.7,
  },
  {
    path: "/resolved",
    title: "Resolved",
    description: "Resolved paper markets and graded outcomes.",
    changeFrequency: "daily",
    priority: 0.6,
  },
  {
    path: "/smart-money",
    title: "Smart money",
    description: "Smart-money research views for paper markets.",
    changeFrequency: "daily",
    priority: 0.55,
  },
  {
    path: "/alerts",
    title: "Alerts",
    description: "Signal alerts digest for paper research (notify/read only).",
    changeFrequency: "weekly",
    priority: 0.45,
  },
];

export function absoluteUrl(path = "/"): string {
  if (!path || path === "/") return SITE_URL;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Build per-route Metadata with title, description, Open Graph, and Twitter cards. */
export function pageMetadata(input: {
  title: string;
  description: string;
  path: string;
  noIndex?: boolean;
}): Metadata {
  // Short segment title so root `title.template` (`%s — AlphaEdge`) applies once.
  const segmentTitle = input.title.replace(new RegExp(`\\s*—\\s*${SITE_NAME}$`), "").trim();
  const fullTitle =
    segmentTitle === DEFAULT_TITLE || segmentTitle.includes(SITE_NAME)
      ? segmentTitle
      : `${segmentTitle} — ${SITE_NAME}`;
  const url = absoluteUrl(input.path);

  return {
    title: segmentTitle,
    description: input.description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      url,
      siteName: SITE_NAME,
      title: fullTitle,
      description: input.description,
      locale: "en_US",
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description: input.description,
    },
    robots: input.noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true },
  };
}
