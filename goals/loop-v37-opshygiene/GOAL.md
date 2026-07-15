# Loop V37 — Ops hygiene (logs, gauges, retention)
> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop37-opshygiene,
> branch loop37/opshygiene. Constitution rules apply.
## Tickets (fix(loop37): <ticket>)
- H1 Live-tick 404 spam: prod logs repeat "Live tick fetch failed ... 404"
  endlessly for delisted venue slugs. Add per-slug failure backoff/demotion
  in the live-tick path (after N consecutive 404s, demote the market to the
  V34 lifecycle-locked handling or skip with ONE structured warning per
  hour). Never silently drop non-404 errors. Tests.
- H2 Connector-health gauges: E2 stubbed alphaedge_connector_health{source}
  in /metrics; verify C1's get_source_health() registry is actually wired
  into it — if not, wire (read both first). Test asserts gauge exposition.
- H3 JobRun retention: bounded sweep (flag-gated, default on, in-process +
  ARQ dual wiring, heartbeat name jobrun_retention registered in
  _ALL_LOOPS/LOOP_INTERVALS) deleting JobRun rows older than
  JOBRUN_RETENTION_DAYS (default 30). Idempotent, batched. Tests.
- H4 Full gate (counts) + ruff + fresh verifier. STOP.
## Ownership: the specific paths above + tests + goals/loop-v37-opshygiene/**;
claims for shared files; migration 048+ only if truly needed (id<=32 chars).
FOREIGN: forecast_autolock/external_market* (V33/Opus owns them RIGHT NOW),
frontend, deploy configs. PAPER_TRADING_ONLY; never push/merge.
