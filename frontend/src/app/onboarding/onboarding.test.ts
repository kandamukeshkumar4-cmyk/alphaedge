import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { isFirstRun, markOnboarded, resetOnboarding } from "@/lib/onboarding";

function createStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
    removeItem: (key: string) => {
      values.delete(key);
    },
  } as Storage;
}

describe("onboarding storage", () => {
  beforeEach(() => {
    vi.stubGlobal("window", { localStorage: createStorage() });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("detects an uncompleted first run", () => {
    expect(isFirstRun()).toBe(true);
  });

  it("marks the tour complete", () => {
    markOnboarded();

    expect(isFirstRun()).toBe(false);
  });

  it("can reset a completed tour", () => {
    markOnboarded();
    resetOnboarding();

    expect(isFirstRun()).toBe(true);
  });
});
