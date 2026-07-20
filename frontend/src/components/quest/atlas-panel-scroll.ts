/**
 * Loop V77 A1 — scroll the ATLAS panel's own overflow container.
 * Never call Element.scrollIntoView (that scrolls the page / window).
 */

export const ATLAS_ANSWER_HIGHLIGHT_MS = 1600;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

/** Scroll `container` so `anchor` sits at the top of the panel viewport. */
export function scrollPanelAnchorToTop(
  container: HTMLElement,
  anchor: HTMLElement,
): void {
  const relativeTop =
    anchor.getBoundingClientRect().top -
    container.getBoundingClientRect().top +
    container.scrollTop;
  const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";
  container.scrollTo({ top: Math.max(0, relativeTop), behavior });
}

/** Whether an assistant message index should receive the arrival highlight. */
export function isHighlightedAnswer(
  role: "user" | "assistant",
  index: number,
  highlightedIndex: number | null,
): boolean {
  return role === "assistant" && highlightedIndex !== null && index === highlightedIndex;
}
