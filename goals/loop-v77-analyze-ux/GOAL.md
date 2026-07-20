# Loop V77 — AI Analyze: visibility, thinking state, decision-grade depth

USER-REPORTED (three distinct problems, all must be fixed):
1. "When I click Analyze it goes UP" — the answer appears somewhere the user
   isn't looking; they don't understand what happened. It must arrive at the
   SIDE, obviously and immediately.
2. "There is no thinking going on" — no visible in-progress state, so the app
   looks dead while the backend composes the analysis.
3. "This data is not enough to even take a decision" — the analyze payload is
   too thin: repeated identical driver labels ("Price Jump" x3), model
   probability often unavailable, no context the user can act on.

Current surfaces: frontend/src/components/quest/AtlasPanel.tsx (desktop right
aside w-320px + mobile bottom sheet, scrollIntoView at ~L45),
backend/app/api/v1/assistant.py (analyze composition ~L421-575).

## Tickets (one commit each, feat(loop77): <ticket>) + tests

- A1 VISIBILITY: clicking Analyze must (a) open/expand the side panel if
  collapsed, (b) make the new answer land in view WITHOUT the page jumping —
  scroll the PANEL's own container, never the window; anchor the newest answer
  at the TOP of the panel viewport (not bottom-scrolled off), (c) on mobile
  open the sheet already scrolled to the answer, (d) briefly highlight the new
  answer block so the eye finds it. No layout shift on the page behind.
- A2 THINKING STATE: an explicit staged progress indicator while the request
  is in flight — visible label that changes with real phases (e.g. "Reading
  market data..." -> "Checking signals..." -> "Composing analysis...") driven
  by elapsed time or streamed phases, plus a skeleton of the answer block.
  Must be visible in the panel where the answer will appear. Never fake
  completion; if the request fails, show an honest error with retry.
- A3 DECISION-GRADE DATA (backend, assistant.py analyze intent): make the
  payload sufficient to reason with. Required additions, all from REAL stored
  data (never fabricate; omit honestly when unavailable):
    * de-duplicate drivers by signal type — never repeat the same label; merge
      into one line with net direction and magnitude
    * price context: current, 24h move, 7d range if stored, volume percentile
    * model view: model probability + edge vs market when available; when not,
      say exactly why in one clause (already partly present — keep honest)
    * market context block (whale pressure, venue gap, news tone) from the
      existing /markets/{slug}/context service when present
    * time context: time to close, whether a locked forecast exists
    * a short "what would change this" line naming the 1-2 observable
      conditions that would flip the read (from real thresholds, not invented)
  Keep the assistant analysis-only: NO recommendations, no bet sizing, no
  advice language, no fabricated numbers. Existing never-rules stay.
- A4 Frontend renders the richer payload readably: grouped sections with
  clear labels, numbers aligned, absent fields omitted (never "N/A" noise),
  the paper-trading truth still visible.
- A5 Gates: backend (ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q
  -p no:cacheprovider, CHECK COUNTS; ruff) + frontend (typecheck, lint,
  vitest, build). Counts in STATE.md.

Constraints: no new UI libraries; follow frontend/.claude/CLAUDE.md tokens;
prefers-reduced-motion respected for the highlight/animation; never touch
order/trade mutation paths; never push/merge.
Exit: A1-A5 DONE or BLOCKED in goals/loop-v77-analyze-ux/STATE.md.
