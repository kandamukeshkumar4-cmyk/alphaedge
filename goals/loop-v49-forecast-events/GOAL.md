# Loop V49 — Forecast lifecycle events (queued for Codex after V42)
> Runner: Codex CLI. Worktree E:/polymarket-worktrees/loop49-forecast-events,
> branch loop49/fc-events.
## Mission: locks/resolutions/scores happen silently. Publish them as events
so watchers of a market SEE the model act.
## Tickets (feat(loop49): <ticket>)
- E1 WS: publish forecast.locked / market.resolved / forecast.scored frames
  on the existing multiplex hub as a `forecasts` channel (E03 pattern);
  emit from the autolock/resolve/score paths via never-raises hooks (the
  accepted observation pattern — NO semantic changes to those paths).
- E2 Notifications: users WATCHING a market (watchlist join) get an in-app
  notification on forecast.locked and market.resolved for it — reuse V24
  producers/never-raises isolation; dedupe per user+market+event.
- E3 Tests (hook isolation: a failing publish never breaks lock/resolve;
  watcher targeting; dedupe) + full gate (COUNTS + ruff) + fresh verifier.
  STOP.
## Ownership: hooks at the three call sites + notification producer + tests
+ goals/loop-v49-forecast-events/**; claims for shared files. SACRED: zero
behavior change to lock/resolve/score semantics; PAPER_TRADING_ONLY; never
push/merge.
