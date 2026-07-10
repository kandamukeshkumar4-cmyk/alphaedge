import { describe, expect, it } from "vitest";
import {
  buildEvidenceIndex,
  evidenceKey,
  extractSignalEvidence,
} from "./signal-evidence";

describe("extractSignalEvidence", () => {
  it("extracts news headline, url, and model-vs-market edge for news:mispricing", () => {
    const ev = extractSignalEvidence("news:mispricing", {
      model_p: 0.62,
      market_p: 0.5,
      gap: 0.12,
      news_url: "https://example.test/news/lal-injury",
      headline: "Lakers star ruled out",
    });
    expect(ev).toEqual({
      kind: "news",
      headline: "Lakers star ruled out",
      url: "https://example.test/news/lal-injury",
      modelP: 0.62,
      marketP: 0.5,
      edgeLabel: "+12.0 pts",
    });
  });

  it("falls back to model-minus-market when gap is absent", () => {
    const ev = extractSignalEvidence("news:mispricing", {
      model_p: 0.4,
      market_p: 0.5,
      headline: "Report",
    });
    expect(ev).toMatchObject({ edgeLabel: "-10.0 pts", url: null });
  });

  it("returns null for news mispricing without a headline", () => {
    expect(extractSignalEvidence("news:mispricing", { model_p: 0.6 })).toBeNull();
  });

  it("returns the neutral catalyst note for anomaly:unusual_flow", () => {
    const ev = extractSignalEvidence("anomaly:unusual_flow", {
      catalyst: "none_found",
      note: "No public catalyst found in the news window.",
    });
    expect(ev).toEqual({
      kind: "catalyst",
      note: "No public catalyst found in the news window.",
    });
  });

  it("defaults the catalyst note when catalyst is none_found but note is blank", () => {
    const ev = extractSignalEvidence("anomaly:unusual_flow", { catalyst: "none_found" });
    expect(ev).toMatchObject({ kind: "catalyst" });
  });

  it("returns null for unrelated signal types", () => {
    expect(extractSignalEvidence("screener:momentum", { headline: "x" })).toBeNull();
    expect(extractSignalEvidence("news:mispricing", null)).toBeNull();
  });
});

describe("buildEvidenceIndex", () => {
  it("indexes by platform+market+family, first wins", () => {
    const index = buildEvidenceIndex([
      {
        signal_type: "news:mispricing",
        platform: "polymarket",
        market_id: "pm-x",
        payload: { headline: "New" },
      },
      {
        signal_type: "news:mispricing",
        platform: "polymarket",
        market_id: "pm-x",
        payload: { headline: "Old" },
      },
    ]);
    const key = evidenceKey("polymarket", "pm-x", "news:mispricing");
    expect((index.get(key) as { headline: string }).headline).toBe("New");
  });
});
