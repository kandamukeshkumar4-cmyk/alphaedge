import { describe, expect, it } from "vitest";

import {
  API_DEGRADED_BANNER_MESSAGE,
  API_DOWN_BANNER_MESSAGE,
} from "./HealthBanner";

describe("HealthBanner copy (loop67 L3)", () => {
  it("uses honest backend-unreachable language when API is down", () => {
    expect(API_DOWN_BANNER_MESSAGE.toLowerCase()).toContain("backend unreachable");
    expect(API_DOWN_BANNER_MESSAGE.toLowerCase()).toContain("will not invent");
    expect(API_DOWN_BANNER_MESSAGE.toLowerCase()).not.toContain("showing sample data");
  });

  it("does not claim degraded APIs are fully healthy with fabricated metrics", () => {
    expect(API_DEGRADED_BANNER_MESSAGE.toLowerCase()).toContain("degraded");
    expect(API_DEGRADED_BANNER_MESSAGE.toLowerCase()).toContain("no fabricated");
  });
});
