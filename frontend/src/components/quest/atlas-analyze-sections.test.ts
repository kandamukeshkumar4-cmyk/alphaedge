import { describe, expect, it } from "vitest";

import {
  isSectionedAnalyzeReply,
  parseAtlasAnalyzeSections,
  splitMetricPairs,
} from "./atlas-analyze-sections";

const SAMPLE = `Paper-trade analysis for Lakers vs Celtics.
**Price:** YES ~54¢ (54.0%), volume $1,000, volume percentile 72.
**24h move:** +2.0% (from 52.0% → 54.0%).
**7d range:** 48.0% – 56.0%.
**Model:** model 58.0% vs market 54.0% (edge +4.0%).
**Drivers:**
- Price Jump (favors YES): Price Jump signal, 3 events, net +12¢
**Market context:** whale pressure +0.30, venue gap +1.5%, news tone positive (+0.20).
**Time:** 12.5h until stored lock time; no locked forecast yet.
**What would change this:** model–market gap shrinking below 2pp (now 4.0%).
Uncertainty: forecasts are provisional; absent fields above were omitted, not invented.
Analysis only — this assistant cannot place trades. Paper trading only — simulated funds, no execution.`;

describe("atlas-analyze-sections (Loop V77 A4)", () => {
  it("parses labeled sections and omits inventing absent ones", () => {
    const { preamble, sections, footer } = parseAtlasAnalyzeSections(SAMPLE);
    expect(preamble[0]).toContain("Paper-trade analysis");
    const labels = sections.map((s) => s.label);
    expect(labels).toEqual([
      "Price",
      "24h move",
      "7d range",
      "Model",
      "Drivers",
      "Market context",
      "Time",
      "What would change this",
    ]);
    expect(labels).not.toContain("N/A");
    const drivers = sections.find((s) => s.key === "drivers");
    expect(drivers?.lines.some((l) => l.includes("Price Jump"))).toBe(true);
    expect(footer.join(" ")).toContain("Analysis only");
    expect(footer.join(" ")).toContain("Paper trading only");
  });

  it("detects sectioned analyze replies and leaves plain chat alone", () => {
    expect(isSectionedAnalyzeReply(SAMPLE)).toBe(true);
    expect(isSectionedAnalyzeReply("Hello, how can I help?")).toBe(false);
  });

  it("splits metric pairs without fabricating values", () => {
    const pairs = splitMetricPairs("YES ~54¢ (54.0%), volume $1,000");
    expect(pairs.length).toBeGreaterThanOrEqual(2);
    expect(pairs.every((p) => p.value.length > 0)).toBe(true);
    expect(pairs.some((p) => /N\/A/i.test(p.value))).toBe(false);
  });
});
