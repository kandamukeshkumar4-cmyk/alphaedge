import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AlertToastCard } from "./AlertToast";
import type { SignalAlert } from "@/hooks/useSignalAlerts";

// Loop V78 (N5) — the Polymarket-style alert card: real title (never the raw
// slug), real venue avatar with glyph fallback, real prices/volume/counts,
// and informational branding only (no danger-red error styling).

const VENUE_IMAGE =
  "https://polymarket-upload.s3.us-east-2.amazonaws.com/elon-musk-abc123.jpg";

const baseToast: SignalAlert = {
  id: "sig-1",
  signalType: "delta:price_jump",
  marketTitle: "Will Elon Musk post 100 times this week?",
  confidencePct: 5,
  createdAt: "2026-07-20T12:00:00Z",
  marketSlug: "pm-musk-posts-week",
  categoryLabel: "Culture",
  icon: "🐦",
  imageUrl: VENUE_IMAGE,
  volume: 52_617_317,
  traders: 1_234,
  marketCount: 38,
  outcomes: [
    { name: "Yes", price: 0.39, imageUrl: VENUE_IMAGE },
    { name: "No", price: 0.61, imageUrl: null },
  ],
};

function renderCard(toast: Partial<SignalAlert> = {}): string {
  return renderToStaticMarkup(
    React.createElement(AlertToastCard, { toast: { ...baseToast, ...toast } }),
  );
}

describe("AlertToastCard", () => {
  it("renders the real market title, not the slug", () => {
    const html = renderCard();
    expect(html).toContain("Will Elon Musk post 100 times this week?");
    expect(html).not.toContain("pm-musk-posts-week</");
  });

  it("humanizes a raw slug when no real title exists", () => {
    const html = renderCard({ marketTitle: "pm-elon-musk-posts-week" });
    expect(html).toContain("Elon musk posts week");
    expect(html).not.toContain("pm-elon-musk-posts-week");
  });

  it("renders the venue avatar image when a real url is present", () => {
    const html = renderCard();
    expect(html).toContain("<img");
    expect(html).toContain(VENUE_IMAGE);
  });

  it("falls back to the glyph token when no image exists", () => {
    const html = renderCard({
      imageUrl: null,
      outcomes: [
        { name: "Yes", price: 0.39, imageUrl: null },
        { name: "No", price: 0.61, imageUrl: null },
      ],
    });
    expect(html).not.toContain("<img");
    expect(html).toContain("🐦");
  });

  it("never hotlinks an arbitrary non-venue host", () => {
    const evil = "https://evil.example.com/musk-fake.jpg";
    const html = renderCard({
      imageUrl: evil,
      outcomes: [{ name: "Yes", price: 0.39, imageUrl: evil }],
    });
    expect(html).not.toContain("evil.example.com");
    expect(html).toContain("🐦");
  });

  it("renders real outcome prices as % pill + multiplier, and the muted footer", () => {
    const html = renderCard();
    expect(html).toContain("39%");
    expect(html).toContain("61%");
    expect(html).toContain("2.56x"); // 1 / 0.39
    expect(html).toContain("1.64x"); // 1 / 0.61
    expect(html).toContain("$52,617,317");
    expect(html).toContain("38 markets");
  });

  it("omits outcome rows and footer honestly when no stored data exists", () => {
    const html = renderCard({
      imageUrl: null,
      volume: null,
      traders: null,
      marketCount: null,
      outcomes: [],
    });
    expect(html).not.toContain("<img");
    expect(html).not.toContain("vol</span>");
    expect(html).not.toContain("markets</span>");
    // Title + category label still render.
    expect(html).toContain("Will Elon Musk post 100 times this week?");
    expect(html).toContain("Culture");
  });

  it("uses informational branding only — never danger-red error styling", () => {
    const html = renderCard();
    expect(html).not.toContain("danger");
    expect(html).not.toContain("text-down");
    expect(html).not.toContain("bg-down");
  });
});
