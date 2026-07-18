import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import AboutPage from "./page";
import { PAPER_TRADING_DISCLAIMER } from "@/lib/paper-trading";

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

describe("/about page (loop67 L1)", () => {
  const html = renderToStaticMarkup(React.createElement(AboutPage));

  it("uses the exact PAPER_TRADING_DISCLAIMER language", () => {
    expect(html).toContain(PAPER_TRADING_DISCLAIMER);
  });

  it("explains paper-trading research scope and no real-money execution", () => {
    expect(html).toContain("paper-trading prediction research");
    expect(html).toContain("simulated funds");
    expect(html).toContain("not financial advice");
    expect(html).toContain("no real-money execution");
  });

  it("explains how forecasts lock and are scored", () => {
    expect(html).toContain("locked forecast");
    expect(html).toContain("Brier score");
  });

  it("links to the live /eval proof dashboard", () => {
    expect(html).toContain('href="/eval"');
  });
});
