# Loop V31 — Sports signal breadth (multi-league ESPN)

> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop31-sports, branch
> loop31/sports. Constitution rules apply.

## Ownership
YOURS: backend/app/data/connectors/sports_results.py + its tests,
backend/app/api/v1/sports.py (additive), goals/loop-v31-sports/**.
Shared files via claims. FOREIGN: everything else; resolution stays with
external_resolve — this remains SIGNALS ONLY (the C2 guards must survive).

## Tickets (continuous; commit feat(loop31): <ticket>)
- L1 Generalize the ESPN connector from NBA-only to a config-driven league
  list (nba, nfl, mlb, plus espn soccer leagues incl. FIFA WC): league ->
  scoreboard path map, per-league source names in the health registry
  (espn-nba, espn-nfl, ...), same keyless path, same final-only rule, same
  non-resolution disclaimers. Fixture tests per league (capture one real
  sample payload each into fixtures — no live network in tests).
- L2 API surface: extend /api/v1/sports/results with a league param
  (additive, default nba) + admin sources reflect per-league health.
- L3 Config: SPORTS_LEAGUES_ENABLED csv setting (default nba); wire into the
  existing sports polling path so only enabled leagues fetch.
- L4 Local soak: enabled=nba,nfl (compressed run), paste per-league
  success/fail counts from /api/v1/system/sources, zero unhandled
  exceptions. Full gate (counts) + fresh verifier each ticket. STOP.
