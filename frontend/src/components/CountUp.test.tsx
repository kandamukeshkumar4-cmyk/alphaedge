import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CountUp, resetCountUpStarted } from "./CountUp";

// Loop V62 (R4) — CountUp renders a span and applies its format. On the server
// it starts at 0 (the count-up runs client-side once in view); the value is
// reached on the client, and immediately for reduced-motion users.
// Loop V71 — value prop changes must clear the one-shot started latch.

describe("CountUp", () => {
  it("renders a span and applies the format function", () => {
    const html = renderToStaticMarkup(
      React.createElement(CountUp, { value: 29, format: (n) => `#${Math.round(n)}` }),
    );
    expect(html).toContain("<span");
    expect(html).toContain("#0");
  });

  it("uses the default integer format without crashing", () => {
    const html = renderToStaticMarkup(React.createElement(CountUp, { value: 42 }));
    expect(html).toContain("<span");
  });
});

describe("resetCountUpStarted (loop71)", () => {
  it("clears the one-shot latch so a new value can re-animate", () => {
    const started = { current: true };
    resetCountUpStarted(started);
    expect(started.current).toBe(false);
  });
});
