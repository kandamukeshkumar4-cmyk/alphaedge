import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { MarketTradingPanel } from "./MarketTradingPanel";

vi.mock("next/link", () => ({
  default: ({ children, ...props }: { children: React.ReactNode }) =>
    React.createElement("a", props, children),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    token: "test-token",
    paperBalance: 1_000,
    refreshBalance: vi.fn(),
  }),
}));

vi.mock("./ToastProvider", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("@/lib/gamification", () => ({
  useGamification: () => ({ markTradePlaced: vi.fn() }),
}));

describe("MarketTradingPanel lifecycle guards", () => {
  it("disables authenticated order controls for a resolved market", () => {
    const html = renderToStaticMarkup(
      <MarketTradingPanel
        slug="resolved-market"
        title="Resolved market"
        status="resolved"
        closeTime="2099-01-01T00:00:00Z"
        initialYesPrice={0}
      />,
    );

    expect(html).toContain(">resolved<");
    expect(html).toContain("Market closed");
    expect(html).not.toContain("Closes");
    expect(html.match(/disabled=""/g)?.length).toBeGreaterThanOrEqual(4);
  });
});
