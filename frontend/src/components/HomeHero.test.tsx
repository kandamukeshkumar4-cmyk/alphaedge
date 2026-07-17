import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HomeHero } from "./HomeHero";

// Loop V62 (R2) — the home hero carries the 15-second comprehension: what the
// app is (honest paper-trading truth) and the three core loops, each deep
// linking to its real surface. These must survive any future copy tweak.

describe("HomeHero", () => {
  const html = renderToStaticMarkup(React.createElement(HomeHero));

  it("states the paper-trading truth plainly", () => {
    expect(html).toContain("paper-trading simulation");
    expect(html).toContain("simulated funds only");
    expect(html).toContain("no real-money execution");
  });

  it("renders the three core loops Predict -> Track -> Prove", () => {
    expect(html).toContain("Predict");
    expect(html).toContain("Track");
    expect(html).toContain("Prove");
  });

  it("deep links each loop to its real surface", () => {
    expect(html).toContain('href="/markets"');
    expect(html).toContain('href="/pods"');
    expect(html).toContain('href="/eval"');
  });

  it("uses no advice language", () => {
    for (const banned of ["you should", "we recommend", "buy now", "guaranteed"]) {
      expect(html.toLowerCase()).not.toContain(banned);
    }
  });
});
