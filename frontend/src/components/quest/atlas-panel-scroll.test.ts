import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ATLAS_ANSWER_HIGHLIGHT_MS,
  isHighlightedAnswer,
  prefersReducedMotion,
  scrollPanelAnchorToTop,
} from "./atlas-panel-scroll";

type FakeEl = {
  getBoundingClientRect: () => DOMRect;
  scrollTop: number;
  scrollTo: ReturnType<typeof vi.fn>;
  scrollIntoView: ReturnType<typeof vi.fn>;
};

function fakeEl(top: number, scrollTop = 0): FakeEl {
  return {
    getBoundingClientRect: () =>
      ({
        top,
        left: 0,
        bottom: top + 80,
        right: 300,
        width: 300,
        height: 80,
        x: 0,
        y: top,
        toJSON: () => ({}),
      }) as DOMRect,
    scrollTop,
    scrollTo: vi.fn(),
    scrollIntoView: vi.fn(),
  };
}

describe("atlas-panel-scroll (Loop V77 A1)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("anchors the answer at the top of the panel container — never uses scrollIntoView", () => {
    const container = fakeEl(100, 40);
    const anchor = fakeEl(220);
    vi.stubGlobal("window", {
      matchMedia: () => ({ matches: false }),
    });

    scrollPanelAnchorToTop(container as unknown as HTMLElement, anchor as unknown as HTMLElement);

    expect(anchor.scrollIntoView).not.toHaveBeenCalled();
    expect(container.scrollTo).toHaveBeenCalledWith({
      // 220 - 100 + 40 = 160 → answer lands at top of panel viewport
      top: 160,
      behavior: "smooth",
    });
  });

  it("uses instant scroll when prefers-reduced-motion is set", () => {
    const container = fakeEl(0, 0);
    const anchor = fakeEl(50);
    vi.stubGlobal("window", {
      matchMedia: () => ({ matches: true }),
    });

    expect(prefersReducedMotion()).toBe(true);
    scrollPanelAnchorToTop(container as unknown as HTMLElement, anchor as unknown as HTMLElement);
    expect(container.scrollTo).toHaveBeenCalledWith({ top: 50, behavior: "auto" });
  });

  it("highlights only the newest assistant answer index", () => {
    expect(isHighlightedAnswer("assistant", 3, 3)).toBe(true);
    expect(isHighlightedAnswer("assistant", 2, 3)).toBe(false);
    expect(isHighlightedAnswer("user", 3, 3)).toBe(false);
    expect(isHighlightedAnswer("assistant", 0, null)).toBe(false);
    expect(ATLAS_ANSWER_HIGHLIGHT_MS).toBeGreaterThan(0);
  });
});
