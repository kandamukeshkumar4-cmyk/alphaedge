import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CoachMarks } from "./CoachMarks";

// Loop V62 (R3) — coach marks must NOT render on the server / first paint: they
// are gated behind mount + a localStorage "seen" flag, so SSR output is empty
// (no hydration flash, no card for returning visitors before the flag check).

describe("CoachMarks", () => {
  it("renders nothing server-side (mount + localStorage gated)", () => {
    const html = renderToStaticMarkup(React.createElement(CoachMarks));
    expect(html).toBe("");
  });
});
