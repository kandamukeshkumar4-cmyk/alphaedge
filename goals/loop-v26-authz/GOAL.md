# Loop V26 — AuthZ matrix & API integration journeys

> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop26-authz, branch
> loop26/authz. Constitution = goals/loop-v15-backend-massive/GOAL.md rules.

## Mission
Lock the security surface: prove every API route enforces exactly the auth it
claims, and codify multi-step API journeys for the wave-2/3 features
(social, notifications, admin) as integration tests. TESTS ONLY — app code
changes are findings, not fixes.

## Ownership
YOURS: backend/tests/** (new files only; never weaken existing tests),
goals/loop-v26-authz/**. FOREIGN: backend/app/** (any needed fix = a SEC
REPORT in STATE.md with repro; do NOT fix), frontend/**, deploy configs.

## Tickets (continuous; commit test(loop26): <ticket>)
- Z1 AuthZ matrix: a parametrized test that walks the OpenAPI snapshot
  (tests/fixtures/openapi_snapshot.json, 154 paths) and asserts each
  operation's response to (a) anonymous, (b) user JWT, (c) admin key:
  expected classes only (2xx/401/403/404/405/422) from an explicit
  allowlist TABLE committed in the test (route -> expected auth class).
  Build the table by READING the routers; any route whose behavior
  surprises you (e.g. public when it looks private) = SEC REPORT entry.
- Z2 Social + notification journeys: user A follows B, B trades (paper),
  A sees it in social/feed AND receives a notification; opt-out hides
  profile + feed rows; read/read-all semantics; WS notifications channel
  frame on new notification (fake WS pattern from test_ws_feed.py).
- Z3 Admin journeys: suspend user -> their paper order 403s -> unsuspend ->
  trades again; market pause -> order rejected; audit rows asserted;
  stats reflect changes (cache-aware).
- Z4 Negative/abuse: cross-user access attempts (A reading B's
  notifications/portfolio), IDOR probes on id-parameter routes from the
  snapshot, oversize/garbage payloads on mutating routes return 4xx never
  5xx. SEC REPORTS for anything that leaks or 500s. Full gate; STOP.

## Gate per ticket
Backend pytest COUNTS + ruff; fresh verifier verdict in STATE.md.
