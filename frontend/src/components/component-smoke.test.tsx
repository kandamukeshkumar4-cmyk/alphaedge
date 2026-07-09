import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { MARKETS } from "../lib/mock-data";
import { AIForecastPanel } from "./AIForecastPanel";
import { LiveTicker } from "./LiveTicker";
import { OrderBook } from "./OrderBook";
import { PriceChart } from "./PriceChart";
import { TradePanel } from "./TradePanel";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => React.createElement("a", { href, ...props }, children),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    token: null,
    refreshBalance: vi.fn(),
  }),
}));

vi.mock("@/hooks/useMarketPrice", () => ({
  useMarketPrice: () => ({
    connected: false,
    yes: 0,
    no: 0,
    ts: null,
  }),
}));

vi.mock("@/components/ToastProvider", () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock("@/lib/alphaedge-api", () => ({
  fetchMarketCandles: vi.fn(async () => null),
}));

describe("critical component smoke tests", () => {
  const market = MARKETS[0];

  it("renders the trade panel logged-out state", () => {
    const html = renderToStaticMarkup(React.createElement(TradePanel, { market }));

    expect(html).toContain("Log in to trade");
    expect(html).toContain("/auth/login");
  });

  it("renders order book bid and ask levels", () => {
    const html = renderToStaticMarkup(React.createElement(OrderBook, { market }));

    expect(html).toContain("Order book");
    expect(html).toContain("Bid (Yes)");
    expect(html).toContain("Ask (No)");
  });

  it("renders AI forecast metrics", () => {
    const html = renderToStaticMarkup(React.createElement(AIForecastPanel, { market }));

    expect(html).toContain("AI forecast");
    expect(html).toContain("Model");
    expect(html).toContain("Calibration (Brier)");
  });

  it("renders live ticker seed rows", () => {
    const html = renderToStaticMarkup(React.createElement(LiveTicker));

    expect(html).toContain("Live trades");
    expect(html).toContain("demo-trader-1");
  });

  it("renders price chart controls before browser chart initialization", () => {
    const html = renderToStaticMarkup(
      React.createElement(PriceChart, {
        slug: market.slug,
        endPrice: market.outcomes[0].price,
      }),
    );

    expect(html).toContain("Market");
    expect(html).toContain("area");
    expect(html).toContain("1d");
  });
});
