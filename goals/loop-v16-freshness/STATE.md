# Loop V16 — Data Freshness & Liveliness (STATE)

Read GOAL.md first. One ticket per iteration. Update EVERY iteration.
Runner: ChatGPT/Codex IDE (local) · worktree E:/polymarket-worktrees/loop16-fresh · branch loop16/freshness.
Orchestrator (Claude main thread) reviews every commit; never push/merge/deploy from here.

## MIGRATION CLAIMS (041+; check loop-v15 STATE.md claims too — 038/039/040 landed)

| Number | Claimed by | Ticket | Status |
|---|---|---|---|
| (none) | | | |

## SHARED FILE CLAIMS (routes.py / ws.py / db/models.py / schemas/** / workers/tasks.py)

| File | Ticket | Status |
|---|---|---|
| `backend/app/api/v1/routes.py` | V1 | RELEASED 2026-07-13T21:17:44-04:00 |

## Tickets

| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| V1 | Trending ranks by recent activity; decided markets out | DONE | Additive `sort=active` ranks open/non-decided markets by 24h price movement, latest recent snapshot, close proximity, sync time, then lifetime volume; Discover, `/markets`, and `/home` consume that order without client-side volume re-sorting. Resolved markets remain reachable through a labeled Longshots / Decided affordance. Full proof and verifier output are in the loop log below. |
| V2 | Live Signals rail: named, valued, deduped | DONE | Raw events optionally join market titles and dedupe identical semantic signals within a requested window while preserving opposite moves and default raw pagination. The rail renders real title, UP/DOWN/INFO, signed bps/¢ or honest Observed, signal label, and relative age; the fabricated whale fallback and repeated em-dash rows are removed. |
| V3 | Ticker freshness: DESC order, dedupe, age, 48h window | DONE | Production source ordering was already correct. Client normalization now sorts REST/WS rows DESC, dedupes bounded semantic repeats while preserving genuine opposite/later moves, shows real signal direction/value/age, and applies `NEXT_PUBLIC_TICKER_MAX_AGE_HOURS` (default 48h). The footer no longer invents trades/sizes or clones quiet rows. Full proof and verifier output are in the loop log below. |
| V4 | F04 forecast auto-lock worker (unblocks grading) | TODO | new workers/forecast_autolock.py; claim tasks.py |
| V5 | Decided/closed market hygiene (no false LIVE chip) | TODO | |
| V6 | [LIVE] end-user re-test proof | TODO | prod READ-ONLY + local stack |

## LOOP LOG (append one entry per iteration; paste gate output tails)

### 2026-07-13 · V1 · DONE

Diagnosis: production default `/api/v1/markets` ranked by lifetime volume, and the frontend re-sorted the response by lifetime volume again. Captured 2026-07-14T00:57:20.9340164Z; the eliminated World Cup teams are honest resolved data, but wrong for Trending.

```json
{
  "before_default_top6": [
    ["pm-will-egypt-win-the-2026-fifa-world-cup", "resolved", 0.0],
    ["pm-will-morocco-win-the-2026-fifa-world-cup-464", "resolved", 0.0],
    ["pm-will-usa-win-the-2026-fifa-world-cup-467", "resolved", 0.0],
    ["pm-will-norway-win-the-2026-fifa-world-cup-893", "resolved", 0.0],
    ["pm-will-argentina-win-the-2026-fifa-world-cup-245", "open", 0.1745],
    ["pm-will-belgium-win-the-2026-fifa-world-cup-358", "resolved", 0.0]
  ],
  "after_policy_projection_top6": [
    ["pm-elon-musk-of-tweets-july-7-july-14-180-199", "open", 0.5255],
    ["pm-elon-musk-of-tweets-july-7-july-14-220-239", "open", 0.0375],
    ["pm-bitcoin-above-60k-on-july-14-2026", "open", 0.982],
    ["pm-bitcoin-above-64k-on-july-14-2026", "open", 0.048],
    ["pm-fifwc-fra-esp-2026-07-14-fra", "open", 0.4037],
    ["pm-fifwc-fra-esp-2026-07-14-esp", "open", 0.2988]
  ]
}
```

Task gate: backend `1416 passed, 28 skipped in 347.86s`; Ruff `All checks passed!`; frontend typecheck and lint passed; Vitest `56 passed (56)`, `344 passed (344)`; Next build compiled and generated 100/100 pages.

```text
=== GATE: backend pytest ===
1416 passed, 28 skipped in 447.40s (0:07:27)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
Test Files  56 passed (56)
Tests  344 passed (344)
PASS frontend test (exit 0)

=== GATE: frontend build ===
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

Fresh-context verifier: PASS — 9 focused backend tests, full backend Ruff, frontend typecheck, 7 focused frontend tests, and `git diff --check` all passed. The Windows pytest temp-cleanup warning occurred after gate exit 0 and is non-blocking.

Manual code-review fallback used because the Superpowers `requesting-code-review` skill is unavailable; the complete diff and every changed line were reviewed, and formatter-only churn in shared `routes.py` was removed before gating. `gh-address-comments`: not applicable (no PR/merge). Bumblebee: not applicable (no manifest, lockfile, dependency loader, or deployment-image change; no merge requested).

AutoLab: baseline=backend 1415 passed/28 skipped and frontend 55 files/341 tests green; prod top six had five resolved 0% rows | benchmark=active-sort focused tests plus full ticket/repo gates | iterations=1, best=backend 1416 passed/28 skipped and frontend 56 files/344 tests | budget=1/3 | outcome=improved

### 2026-07-13 · V2 · DONE

Diagnosis: production `/signals/events` already carried direction, magnitude, bps, and timestamps. The rail joined the slug-valued `market_id` against UUID `market.id`, ignored the payload, and mapped every non-`buy` type to SHORT with an em-dash value. Captured 2026-07-14T01:40:15.8660644Z.

```json
{
  "before_current_mapping": [
    ["POLY", "delta:price_jump", "—"],
    ["POLY", "delta:price_jump", "—"],
    ["POLY", "delta:price_jump", "—"],
    ["POLY", "delta:price_jump", "—"],
    ["POLY", "delta:price_jump", "—"]
  ],
  "after_payload_projection": [
    ["Will Iran announce withdrawal from MOU negotiations by July 31?", "DOWN", "-200 bps"],
    ["Will Alana Haim attend Taylor Swift's wedding?", "UP", "+130 bps"],
    ["Will Elon Musk post 180-199 tweets from July 7 to July 14, 2026?", "UP", "+115 bps"],
    ["Will OpenAI announce earbuds or headphones in 2026?", "DOWN", "-200 bps"],
    ["Will OpenAI announce earbuds or headphones in 2026?", "UP", "+200 bps"]
  ]
}
```

Task gate: backend `1417 passed, 28 skipped in 433.62s`; Ruff `All checks passed!`; frontend typecheck and lint passed; Vitest `58 passed (58)`, `349 passed (349)`; Next build compiled and generated 100/100 pages.

```text
=== GATE: backend pytest ===
1417 passed, 28 skipped in 344.75s (0:05:44)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
Test Files  58 passed (58)
Tests  349 passed (349)
PASS frontend test (exit 0)

=== GATE: frontend build ===
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

Fresh-context verifier: PASS — 5 focused backend tests, full backend Ruff, frontend typecheck, 5 focused frontend tests, and `git diff --check` all passed; changed paths exactly matched the eight-file work order. Windows pytest temp-cleanup warnings occurred after gate exit 0 and are non-blocking.

Manual code-review fallback used because the Superpowers `requesting-code-review` skill is unavailable; complete diff review confirmed dedupe is opt-in, default raw pagination is unchanged, and opposite directions remain distinct. `gh-address-comments`: not applicable (no PR/merge). Bumblebee: not applicable (no manifest, lockfile, dependency loader, or deployment-image change; no merge requested).

AutoLab: baseline=V1 branch gate backend 1416 passed/28 skipped and frontend 56 files/344 tests; live rail projection had five degenerate rows | benchmark=signal view-model/dedupe focused tests plus full ticket/repo gates | iterations=1, best=backend 1417 passed/28 skipped and frontend 58 files/349 tests | budget=1/3 | outcome=improved

### ORCHESTRATOR REVIEW · V1 · bdcc4a9 · verdict: PASS
Exemplary diagnosis — the double volume-sort (backend default + frontend
re-sort) was the true root cause and the fix is additive on both sides.
Evidence quality is the bar for all remaining tickets. Continue V2 (find WHY
five identical price_jump rows exist before touching rendering — suspect the
same event re-emitted by the diff engine or one row rendered per snapshot).
Reminder for V4: claim workers/tasks.py in SHARED FILE CLAIMS before the
append; migration only if genuinely needed (claim 041). Orchestrator reviews
every commit here in STATE.md; a NEEDS-FIX verdict must be fixed before the
next ticket.

### ORCHESTRATOR REVIEW · V2 · 2b00099 · verdict: PASS
Another correct root cause: the payload always had the data — the rail joined
slug-valued market_id against UUID market.id and defaulted to SHORT/em-dash.
Fix is right-shaped (join fixed, payload consumed, backend window dedupe with
tests both sides). Gates green. Continue V3 (ticker) then V4 (forecast
auto-lock — claim workers/tasks.py; note loop15-D may also be appending it
in a parallel worktree, keep your append minimal) then V5, V6.

### 2026-07-13 · V3 · DONE

Diagnosis: production was not emitting an out-of-order feed. At 2026-07-14T02:15:21.8595373Z, both `/signals/events?limit=200` and `/feed?limit=200` were strictly DESC, but 113/200 signal rows were already older than 48h (oldest 51.59h). The footer trusted response order, omitted age, invented trade verbs and dollar sizes from unrelated market volume/index values, and doubled every row into an animated loop. Unified activity only deduped IDs, so a distinct-ID semantic repeat or an older WebSocket insert could still look fresh.

```json
{
  "captured_at": "2026-07-14T02:15:21.8595373+00:00",
  "signals": {"count": 200, "strict_desc": true, "oldest_hours": 51.59, "over_48h": 113},
  "feed": {"count": 200, "strict_desc": true, "oldest_hours": 51.56}
}
```

Fix: the footer now consumes the same real signal view model as the rail, renders persisted direction/value plus relative age, sorts before bounded semantic dedupe, and filters against `NEXT_PUBLIC_TICKER_MAX_AGE_HOURS` (positive hours; default 48). It renders one honest horizontal sequence, so quiet data is not cloned. Unified REST and WebSocket feed rows are normalized DESC and deduped within ten minutes; market-detail activity uses the same signal ordering/dedupe and retains age labels.

Task gate: backend `1417 passed, 28 skipped in 639.86s`; Ruff `All checks passed!`; frontend typecheck and lint passed; Vitest `59 passed (59)`, `354 passed (354)`; Next build compiled and generated 100/100 pages.

```text
=== GATE: backend pytest ===
1417 passed, 28 skipped in 579.57s (0:09:39)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
Test Files  59 passed (59)
Tests  354 passed (354)
PASS frontend test (exit 0)

=== GATE: frontend build ===
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

The Windows pytest temp-directory cleanup warning occurred after gate exit 0 and is non-blocking.

Fresh-context verifier: PASS — 9 focused frontend tests, typecheck, lint, and `git diff --check` passed. The verifier reviewed exactly the eight scoped paths and confirmed DESC ordering, bounded semantic dedupe, preservation of opposite/out-of-window events, configurable default-48h cutoff, real direction/value/age rendering, no cloned ticker loop, and REST/WebSocket normalization. No files were edited by the verifier.

Manual code-review fallback used because the Superpowers `requesting-code-review` skill is unavailable; the complete diff and every changed line were reviewed with no blocking finding. `gh-address-comments`: not applicable (no PR/merge). Bumblebee: not applicable (no manifest, lockfile, dependency loader, or deployment-image change; no merge requested).

AutoLab: baseline=V2 gate backend 1417 passed/28 skipped and frontend 58 files/349 tests; prod sample had 113/200 signal rows older than 48h and the footer cloned all displayed rows | benchmark=freshness/dedupe focused tests plus full ticket/repo gates | iterations=1, best=backend 1417 passed/28 skipped and frontend 59 files/354 tests | budget=1/3 | outcome=improved
