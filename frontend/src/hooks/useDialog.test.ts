import { describe, expect, it } from "vitest";

import { nextTrapIndex } from "./useDialog";

describe("nextTrapIndex (focus-trap wrap-around)", () => {
  it("wraps forward off the last element to the first", () => {
    expect(nextTrapIndex(3, 2, false)).toBe(0);
  });

  it("wraps backward off the first element to the last", () => {
    expect(nextTrapIndex(3, 0, true)).toBe(2);
  });

  it("wraps backward to last when focus is on the container (index -1)", () => {
    expect(nextTrapIndex(3, -1, true)).toBe(2);
  });

  it("lets the browser handle a normal forward tab in the middle", () => {
    expect(nextTrapIndex(3, 1, false)).toBe(-1);
  });

  it("lets the browser handle a normal backward tab in the middle", () => {
    expect(nextTrapIndex(3, 1, true)).toBe(-1);
  });

  it("no-ops an empty dialog", () => {
    expect(nextTrapIndex(0, -1, false)).toBe(-1);
    expect(nextTrapIndex(0, -1, true)).toBe(-1);
  });

  it("single focusable wraps to itself in both directions", () => {
    expect(nextTrapIndex(1, 0, false)).toBe(0);
    expect(nextTrapIndex(1, 0, true)).toBe(0);
  });
});
