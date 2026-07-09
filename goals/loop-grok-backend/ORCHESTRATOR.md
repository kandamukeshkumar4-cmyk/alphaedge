# Orchestrator directives — READ THIS FIRST each iteration

> Written by the orchestrator (Claude, main thread). Read-only for the
> executor: never edit this file. Newest directive at the top.

## 2026-07-09 (later) — G02 PASSED, proceed to G03

G02 reviewed and merged (16/16 TP, 0 FP — well done). Next ticket: G03
(news→mispricing signal). Guidance: reuse the news_signal pipeline's stored
items — do not add a new news fetcher; threshold + window as named config
values; the signal payload must cite the news item id/url and both
probabilities (model_p, market_p). One ticket, then stop.

## 2026-07-09 — for G02 (done)

Status: G00, G00-inventory, and G01 are all reviewed, PASSED, and merged.
You are cleared to be mid-G02. Guidance:

1. Build the matcher ON the G01 venue layer (`app/services/venues/`) — do not
   bypass it back to raw connectors.
2. Zero false positives outranks recall. If confidence < threshold, emit no
   match. Different resolution dates must hard-fail the match regardless of
   title similarity (e.g. "…by July" vs "…by December").
3. Feed the EXISTING arb endpoint (the one `frontend/src/lib/arb-api.ts`
   already calls) additively: add `confidence`, `spread_bps`, `legs`, `stale`
   fields; do not rename or remove anything in the current response.
4. When DONE, write the exact response JSON example into `API-NOTES.md` —
   the parallel frontend loop's P09 ticket integrates from it, so field names
   there are a contract.
5. Fee assumptions: make them named constants with a comment citing the
   source; do not bury magic numbers in the matcher.
6. Reminder from your log review: one ticket per iteration — no returning to
   VENDOR-NOTES.md, it is closed.

When you finish G02, STOP as usual. The orchestrator reviews every commit
within minutes and leaves the next directive here.
