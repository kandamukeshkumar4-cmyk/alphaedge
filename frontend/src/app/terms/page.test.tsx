import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import TermsPage from "./page";
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

describe("/terms page (loop67 L1)", () => {
  const html = renderToStaticMarkup(React.createElement(TermsPage));

  it("uses the exact PAPER_TRADING_DISCLAIMER language", () => {
    expect(html).toContain(PAPER_TRADING_DISCLAIMER);
  });

  it("states not financial advice and simulated funds only", () => {
    expect(html).toContain("Not financial");
    expect(html).toContain("simulated funds");
    expect(html).toContain("No real currency");
  });

  it("links to /eval proof and /about", () => {
    expect(html).toContain('href="/eval"');
    expect(html).toContain('href="/about"');
  });
});
