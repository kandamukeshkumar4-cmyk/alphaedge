# Loop V75 — Settlement unification + resolution worker (QUEUED — launch AFTER V74 merges; shares files)

Fixes verified deep-review findings #3, #4, #5, #8 + unresolved #6.

## Tickets (one commit each, fix(loop75): <ticket>) + tests
- S1 One settlement entrypoint (#4): retire MarketService._settle_positions in
  favor of settlement_service.settle_market; every resolve path (admin UUID,
  admin slug, WC2026 resolver) must also run _settle_paper_orders and write a
  MarketResolution row; remove the CATALOG_SLUGS hard gate (resolve any
  resolvable market). Position.settled set consistently.
- S2 Venue resolution worker (#3): flag-gated in-process loop that finds
  LOCKED live catalog markets whose venue reports a terminal outcome and
  calls the single settlement entrypoint; until resolved, portfolio UI/API
  discloses "locked, unsettled" honestly (no implied terminal PnL).
- S3 Server-side risk inputs (#5): POST /markets/{slug}/orders must not trust
  client edge/confidence/current_drawdown. Either recompute from server
  prediction + book mid, or drop model gates on this path and document it as
  cash/position-gated; drawdown computed from ledger equity. No behavioral
  trust in client risk fields.
- S4 Pod fees honest (#8): debit estimated fee from pod account cash on fill
  (or stop counting fees in exposure and label non-cash); include cumulative
  fees in pod equity snapshots.
- S5 Leakage hardening (unresolved #6): DB constraint/validation that LIVE
  forecast rows have locked_at NOT NULL; migration 055+ (<=32 chars, chain on
  current head).
- S6 Full gate (CHECK COUNTS + ruff); STATE.md with counts.

Constraints: single settlement path is the point — no new special cases;
PAPER_TRADING_ONLY untouched; order path sacred. Never push/merge.
