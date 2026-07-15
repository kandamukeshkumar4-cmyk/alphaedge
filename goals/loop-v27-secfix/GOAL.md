# Loop V27 — Fix V26 SEC findings

> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop27-secfix, branch
> loop27/secfix. Constitution rules apply. The AUTHORITATIVE specs are the
> SEC REPORTS in goals/loop-v26-authz/STATE.md (in your base after sync) —
> read them verbatim; each has exact repro + an xfail test that must flip
> to PASSING (remove the xfail) as part of its fix.

## Tickets (continuous; commit fix(loop27): <SEC-id>)
- X1 SEC-Z2-01: followed-trade notifications — fix social_follow_tables_present()
  to detect the REAL table name (`follows`), and call
  notify_followed_trader_trade from the paper-order fill path with the same
  never-raises isolation as notify_order_filled. Un-xfail
  test_z2_followed_trade_notification_gap.
- X2 SEC-Z2-02: read-all stale unread flags — fix the read-all update to
  cover listed rows atomically; un-xfail its test.
- X3 SEC-Z1-01: admin phase3 snapshot backtest — validate body (422 on
  missing fields), never uncaught; remove from _XFAIL_PROBES.
- X4 Full gate (counts!) + fresh verifier + confirm ZERO xfails remain that
  reference SEC ids. STOP.

## Ownership: the specific files each fix requires + their tests +
goals/loop-v27-secfix/**. Claims for shared files. Never weaken a test —
un-xfailing is the point. PAPER_TRADING_ONLY; order path additive-observation
only (the X1 hook mirrors the existing accepted pattern).
