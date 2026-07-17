import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./EmptyState";
import { ALL_FEATURES } from "@/lib/feature-registry";

// Loop V62 (R3) — the canonical honest empty state must render its "what will
// appear" body and a link to the feeding feature.

describe("EmptyState", () => {
  it("renders title, body and a feeder link", () => {
    const html = renderToStaticMarkup(
      React.createElement(EmptyState, {
        title: "No markets yet",
        body: "Tap the star on any market and it lands here.",
        cta: { href: "/markets", label: "Browse markets" },
        icon: "grid",
      }),
    );
    expect(html).toContain("No markets yet");
    expect(html).toContain("Tap the star on any market and it lands here.");
    expect(html).toContain('href="/markets"');
    expect(html).toContain("Browse markets");
  });

  it("renders without a cta when none is given", () => {
    const html = renderToStaticMarkup(
      React.createElement(EmptyState, { title: "Nothing here", body: "Come back later." }),
    );
    expect(html).toContain("Nothing here");
    expect(html).not.toContain("<a ");
  });
});

describe("NEW badge registry", () => {
  it("flags at least one recently-shipped surface as NEW", () => {
    const flagged = ALL_FEATURES.filter((f) => f.badge === "NEW");
    expect(flagged.length).toBeGreaterThan(0);
    // Pods is the newest command center.
    expect(flagged.some((f) => f.id === "pods")).toBe(true);
  });
});
