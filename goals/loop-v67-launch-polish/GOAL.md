# Loop V67 — Public-launch polish (QUEUED — assign after V62 merges)

## Outcome
The app is presentable to a stranger arriving from a link: proper domain-ready
metadata, honest legal/disclaimer page, graceful failure surfaces. No feature
work.

## Tickets (one commit each, feat(loop67): <ticket>)
- L1 /terms + /about pages: what AlphaEdge is (paper-trading prediction
  research platform, simulated funds, no real-money execution, not financial
  advice — reuse the exact PAPER_TRADING_DISCLAIMER language), how forecasts
  are locked/scored, link to /eval for the live proof. Footer links from
  every page.
- L2 Metadata pass: per-route <title>/description, OpenGraph + twitter cards
  (static OG image fine), favicon set, robots.txt + sitemap for public
  routes only (no admin).
- L3 Failure surfaces: branded 404 and error pages with nav back; global
  error boundary copy that never exposes internals; API-down banner state on
  data-driven pages (honest "backend unreachable", no fake data).
- L4 Lighthouse sanity: run against prod build locally; record perf/a11y/SEO
  scores in STATE.md; fix only cheap wins (<1h each, max 3) — park the rest
  as unresolved with what-to-check-next.
- L5 Gate: typecheck, lint, vitest, build green; counts in STATE.md.

Constraints: frontend only; no new libraries; paper-trading truth everywhere;
never fabricate scores or promise returns. Exit: R1-R5 DONE or BLOCKED in
STATE.md. Never push/merge.

## Orchestrator-side (not runner work)
- Custom domain: user decision + DNS (user action; Vercel/Railway config).
- Railway load sanity: observe under first traffic; scale plan if needed.
