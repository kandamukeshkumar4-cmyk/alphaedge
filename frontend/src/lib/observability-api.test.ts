import { describe, expect, it } from "vitest";

import {
  formatAgeSec,
  heartbeatAgeSec,
  isHeartbeatStale,
} from "./observability-api";

describe("loop heartbeat age helpers", () => {
  const now = Date.parse("2026-07-15T18:00:00Z");

  it("computes age in whole seconds", () => {
    expect(heartbeatAgeSec("2026-07-15T17:59:45Z", now)).toBe(15);
    expect(heartbeatAgeSec(null, now)).toBeNull();
    expect(heartbeatAgeSec("not-a-date", now)).toBeNull();
  });

  it("humanizes age", () => {
    expect(formatAgeSec(null)).toBe("never");
    expect(formatAgeSec(12)).toBe("12s ago");
    expect(formatAgeSec(125)).toBe("2m ago");
    expect(formatAgeSec(7200)).toBe("2h ago");
    expect(formatAgeSec(172800)).toBe("2d ago");
  });

  it("warns when age exceeds 2× interval", () => {
    expect(isHeartbeatStale(61, 30)).toBe(true);
    expect(isHeartbeatStale(60, 30)).toBe(false);
    expect(isHeartbeatStale(10, 30)).toBe(false);
    expect(isHeartbeatStale(null, 30)).toBe(false);
    expect(isHeartbeatStale(100, null)).toBe(false);
    expect(isHeartbeatStale(100, 0)).toBe(false);
  });
});
