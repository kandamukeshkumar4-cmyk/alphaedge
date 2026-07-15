# Loop V33 — Forecast-lock breadth audit (honest accrual acceleration)
> Runner: ChatGPT/Codex IDE. Worktree E:/polymarket-worktrees/loop33-lockbreadth,
> branch loop33/lockbreadth. Advisor waived (DIR-V29-001 precedent).
## Mission
resolved_count accrues only when locked forecasts meet real resolutions.
Audit WHY more open markets are not getting locked pre-close, and widen
eligibility HONESTLY (never lock at/after close; never relax the leakage
gate; never fabricate). More breadth = faster honest accrual toward the 100
threshold.
## Tickets (commit feat(loop33): <ticket>)
- B1 Audit (read-only + report in STATE.md): with a local DB snapshot of the
  eligibility query in workers/forecast_autolock.py, quantify the funnel:
  open markets -> has close_at -> within horizon -> lacks LIVE forecast ->
  batch cap. Which filter excludes the most? Include real prod READ-ONLY api
  counts (markets open vs autolock heartbeat details if exposed).
- B2 Config tuning: based on B1, propose + implement config changes only
  (horizon, batch, pass frequency) within safe bounds; justify each in
  STATE.md. If the model/prediction path rejects some markets (e.g. missing
  features), file findings — do NOT hack predictions.
- B3 Tests for the widened funnel edges; full gate (counts) + verifier. STOP.
## Ownership: workers/forecast_autolock.py config usage + core/config.py
(additive) + tests + goals/loop-v33-lockbreadth/**. Never touch scoring/
resolution; PAPER_TRADING_ONLY; leakage gate sacred.
