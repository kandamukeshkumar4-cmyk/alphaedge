"use client";

import { useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Pure Tab wrap-around decision for a focus trap. `activeIndex` is the index of
 * the focused element in the focusable list, or -1 when focus is on the dialog
 * container itself. Returns the index to move focus to, or -1 to let the
 * browser handle it (focus stays inside without wrapping).
 */
export function nextTrapIndex(count: number, activeIndex: number, shiftKey: boolean): number {
  if (count === 0) return -1;
  const last = count - 1;
  if (shiftKey && activeIndex <= 0) return last; // wrap backwards off the first/container
  if (!shiftKey && activeIndex === last) return 0; // wrap forwards off the last
  return -1;
}

/**
 * Audit H-A11Y-01: the shared modal-dialog behaviour our overlays were missing.
 * Attach the returned ref to the dialog container (the element with
 * role="dialog"). On mount it saves the triggering element, moves focus into
 * the dialog, and traps Tab within it; Escape calls onClose; on unmount it
 * restores focus to the trigger. Works for any conditionally-mounted overlay.
 */
export function useDialog<T extends HTMLElement>(onClose: () => void, active = true) {
  const ref = useRef<T>(null);
  // Keep the latest onClose without re-running the trap effect (which would move
  // focus back to the top on every parent re-render, e.g. a step change).
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    // `active` lets a dialog that is conditionally rendered inside a persistent
    // parent (e.g. the ATLAS mobile sheet) engage the trap when it opens.
    if (!active) return;
    const node = ref.current;
    if (!node) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;

    // Initial focus: first focusable child, else the container itself.
    const focusables = () => Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = focusables()[0];
    (first ?? node).focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const active = document.activeElement as HTMLElement | null;
      const activeIndex = active ? items.indexOf(active) : -1;
      const target = nextTrapIndex(items.length, activeIndex, e.shiftKey);
      if (target >= 0) {
        e.preventDefault();
        items[target].focus();
      }
    }

    node.addEventListener("keydown", onKeyDown);
    return () => {
      node.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [active]);

  return ref;
}
