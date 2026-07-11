import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { RouteError } from "./RouteError";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => React.createElement("a", { href, ...props }, children),
}));

// Walk a rendered React element tree to find the first <button>.
function findButton(node: unknown): React.ReactElement | null {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = findButton(child);
      if (found) return found;
    }
    return null;
  }
  const el = node as React.ReactElement<{ children?: unknown }>;
  if (el.type === "button") return el;
  return findButton(el.props?.children);
}

describe("RouteError shared fallback (U01)", () => {
  it("renders a friendly message, retry button, and home link", () => {
    const html = renderToStaticMarkup(
      React.createElement(RouteError, { reset: () => {} }),
    );

    expect(html).toContain("Something went wrong");
    expect(html).toContain("Try again");
    expect(html).toContain('href="/"');
    expect(html).toContain("Back home");
  });

  it("Try again calls the reset prop", () => {
    const reset = vi.fn();
    const tree = RouteError({ reset }) as React.ReactElement;
    const button = findButton(tree);

    expect(button).toBeTruthy();
    (button!.props as { onClick: () => void }).onClick();

    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("omits the retry button when no reset is provided", () => {
    const html = renderToStaticMarkup(React.createElement(RouteError, {}));

    expect(html).not.toContain("Try again");
    // Home link is always present so the user is never stranded.
    expect(html).toContain('href="/"');
  });

  it("shows the error digest ref when present for support tracing", () => {
    const html = renderToStaticMarkup(
      React.createElement(RouteError, {
        reset: () => {},
        error: Object.assign(new Error("boom"), { digest: "abc123" }),
      }),
    );

    expect(html).toContain("abc123");
    // The raw error message must never leak into the UI.
    expect(html).not.toContain("boom");
  });
});
