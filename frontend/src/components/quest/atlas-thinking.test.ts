import { describe, expect, it } from "vitest";

import {
  ATLAS_THINKING_PHASES,
  atlasNextPhaseBoundaryMs,
  atlasThinkingPhaseAt,
} from "./atlas-thinking";

describe("atlas-thinking (Loop V77 A2)", () => {
  it("starts on Reading market data and advances by elapsed time only", () => {
    expect(atlasThinkingPhaseAt(0).label).toBe("Reading market data…");
    expect(atlasThinkingPhaseAt(1199).id).toBe("read");
    expect(atlasThinkingPhaseAt(1200).label).toBe("Checking signals…");
    expect(atlasThinkingPhaseAt(2799).id).toBe("signals");
    expect(atlasThinkingPhaseAt(2800).label).toBe("Composing analysis…");
    expect(atlasThinkingPhaseAt(60_000).id).toBe("compose");
  });

  it("never fabricates a done phase — last stage stays composing", () => {
    const labels = ATLAS_THINKING_PHASES.map((p) => p.label.toLowerCase());
    expect(labels.some((l) => l.includes("done") || l.includes("complete"))).toBe(false);
    expect(atlasNextPhaseBoundaryMs(0)).toBe(1200);
    expect(atlasNextPhaseBoundaryMs(1200)).toBe(2800);
    expect(atlasNextPhaseBoundaryMs(2800)).toBeNull();
  });
});
