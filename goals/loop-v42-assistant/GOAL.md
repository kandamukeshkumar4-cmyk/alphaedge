# Loop V42 — Assistant intelligence depth
> Runner: ChatGPT/Codex IDE. Worktree E:/polymarket-worktrees/loop42-assistant,
> branch loop42/assistant. Advisor waived (DIR-V29-001 precedent).
## Mission: V41 made Analyze honest; now make it SMART. The reply says
"Model probability: not available — omitted" for most markets, and the
exposure/bear-case intents are shallow. Deepen using ONLY existing services.
## Tickets (feat(loop42): <ticket>)
- M1 Model probability on demand: when the analyze intent runs and no stored
  prediction exists for the market, call the EXISTING prediction/feature
  pipeline (read how /markets/{slug} prediction endpoints do it) with a short
  in-process cache (<=60s, leaderboard_cache pattern). If the model
  genuinely can't score the market (missing features), say why in one honest
  clause. Never invent.
- M2 Bear-case intent depth: compose from real data — top negative drivers,
  recent adverse price moves, liquidity thinness (volume percentile vs
  catalog), time-to-close risk. Cited from services; omissions honest.
- M3 Exposure intent depth (auth users): current position in THIS market +
  portfolio concentration % + what a resolution against would do to balance
  (pure math on existing positions; no advice language — descriptive only).
- M4 Tests for each intent (with/without data) + full gate (COUNTS + ruff)
  + fresh verifier. STOP.
## Ownership: assistant path + tests + goals/loop-v42-assistant/**; claims
for shared files. Analysis-only stays sacred: no order-path imports, no
advice/recommendation language ("you should buy" = NEEDS-FIX), disclaimers
intact. PAPER_TRADING_ONLY; never push/merge.
