import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import NotFound from "./not-found";

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

describe("branded not-found (loop67 L3)", () => {
  const html = renderToStaticMarkup(React.createElement(NotFound));

  it("renders a 404 heading and nav back links", () => {
    expect(html).toContain("This page does not exist");
    expect(html).toContain("404");
    expect(html).toContain('href="/"');
    expect(html).toContain('href="/markets"');
    expect(html).toContain('href="/about"');
  });

  it("refuses to invent data for a missing route", () => {
    expect(html).toContain("will not invent markets or scores");
  });
});
