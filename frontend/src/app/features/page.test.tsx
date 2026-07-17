import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import FeaturesPage from "./page";
import { ALL_FEATURES, FEATURE_GROUPS } from "@/lib/feature-registry";

// Loop V62 (R1) — the /features map must list every registered capability with
// its label + real deep link, and keep the paper-trading truth visible. It is
// the discoverability backstop: nothing ships without a surface here.

// renderToStaticMarkup HTML-escapes text content (e.g. "&" -> "&amp;").
const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

describe("/features map page", () => {
  const html = renderToStaticMarkup(React.createElement(FeaturesPage));

  it("keeps the paper-trading truth visible and honest", () => {
    expect(html).toContain("paper-trading simulation");
    expect(html).toContain("no real money is ever used");
  });

  it("renders every group title", () => {
    for (const group of FEATURE_GROUPS) {
      expect(html).toContain(esc(group.title));
    }
  });

  it("renders every feature label and its deep link", () => {
    for (const feature of ALL_FEATURES) {
      expect(html).toContain(esc(feature.label));
      expect(html).toContain(`href="${feature.href}"`);
    }
  });

  it("surfaces the core loops markets, eval and pods", () => {
    expect(html).toContain('href="/markets"');
    expect(html).toContain('href="/eval"');
    expect(html).toContain('href="/pods"');
  });

  it("marks embedded/overlay surfaces so their real home is discoverable", () => {
    // AI Analyze is an overlay opened from a market — the note must say so.
    expect(html).toContain("Open the ✦ AI Analyze panel from any market.");
    // Heartbeat decision log lives inside Pods.
    expect(html).toContain("The live decision log runs inside Pods.");
  });
});
