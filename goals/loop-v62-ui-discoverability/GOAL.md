# Loop V62 — UI discoverability redesign (QUEUED for OpenCode Kimi K3 after V60)

## The 15-second rule (binding design principle)
A first-time visitor must understand WHAT the app does and WHERE every major
feature lives within 15 seconds. Nothing hidden: every shipped feature is
reachable from a visible, labeled surface. Graphics and motion are
first-class: premium animations (respect prefers-reduced-motion), purposeful
transitions, zero jank.

## Scope: frontend only. Follow frontend/.claude/CLAUDE.md design system
(tokens, dark-first). No new UI libraries. Do not touch order/trade mutation
logic.

## Feature inventory that MUST be discoverable (verify each; cite route)
Markets browse + detail (candles, orderbook, locked-forecast panel), AI
Analyze assistant, /eval proof dashboard (cluster gate, composition, drift),
/pods command center, heartbeat decision log, market context panel
(whales/gaps/news), notifications bell, trader profiles + following, social
feed, portfolio + paper trading, admin (authed), system status.

## Tickets (one commit each, feat(loop62): <ticket>)
- R1 Information architecture: global nav overhaul — grouped, labeled,
  icon+text (no icon-only mystery meat); mobile parity; active-state
  clarity; a /features map page listing every capability with one-line
  what-it-does + deep link.
- R2 Home hero rework: 15-second comprehension — what the app is (honest
  paper-trading copy), the three core loops (Predict -> Track -> Prove) as
  animated cards deep-linking to markets, /pods, /eval; scroll-reveal per
  existing animation patterns.
- R3 Feature spotlight: first-visit coach marks (dismissable, localStorage
  'seen' flag only — never auth data) highlighting nav groups; "NEW" badges
  from a registry file; empty states on every page explain what will appear
  and link to the feature that feeds it.
- R4 Motion pass: consistent enter/hover/transition system (150-250ms,
  shared easing tokens), animated number tickers, chart reveals,
  decision-log blink — all gated by prefers-reduced-motion.
- R5 Discoverability audit table in STATE.md: feature -> route -> clicks
  from home (<=2) -> visible label. Fix misses.
- R6 Gate: typecheck, lint, vitest, build green; Playwright smoke on nav +
  /features; counts in STATE.md.

NEVER: fabricate data, advice language, hide the paper-trading truth, push,
merge. Stop when R1-R6 DONE or BLOCKED in STATE.md.
