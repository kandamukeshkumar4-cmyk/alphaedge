import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import PodsPage from "./page";

// Loop V60 (U2) — the /pods shell must always carry the honest paper banner,
// even in the first (loading) paint, and must never pre-render fleet numbers.
describe("/pods page shell", () => {
  it("renders the header and the simulated-funds banner in the initial paint", () => {
    const html = renderToStaticMarkup(React.createElement(PodsPage));

    expect(html).toContain("Pods");
    expect(html).toContain("Simulated funds — no execution");
    expect(html).toContain("paper-trading telemetry only");
  });

  it("shows skeleton cards (no fabricated pod data) before the first fetch resolves", () => {
    const html = renderToStaticMarkup(React.createElement(PodsPage));

    expect(html).toContain("skeleton");
    expect(html).not.toContain("Last decision");
    expect(html).not.toContain("Bankroll");
  });
});
