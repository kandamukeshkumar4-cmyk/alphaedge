import { describe, expect, it } from "vitest";

import { classifyHealth } from "./useApiHealth";

// O08 (E-test-debt): the live/demo classification had no test. Cover the four
// decision branches the header LIVE/DEMO badge depends on.
describe("classifyHealth", () => {
  it("is demo when no API base is configured", () => {
    expect(classifyHealth("", { ok: true })).toBe("demo");
    expect(classifyHealth("", null)).toBe("demo");
  });

  it("is live when the backend responds ok", () => {
    expect(classifyHealth("http://localhost:8000", { ok: true })).toBe("live");
  });

  it("is demo when the backend responds non-ok", () => {
    expect(classifyHealth("http://localhost:8000", { ok: false })).toBe("demo");
  });

  it("is demo when the fetch throws (backend unreachable)", () => {
    expect(classifyHealth("http://localhost:8000", null)).toBe("demo");
  });
});
