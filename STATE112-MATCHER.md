# STATE112-MATCHER — reachable venue matching per MATCHER-DIAG112

**Role:** Implementation engineer (loop112-matcher worktree)
**Work order:** `MATCHER-DIAG112.md` → "Junior-implementable fix plan"
**Charter:** `backend/app/services/venue_match_service.py` + `backend/tests/test_loop112_matcher.py`
(new) + this file + `backend/app/core/config.py` (plan adds a tunable) +
`backend/app/signals/matching.py` — see charter note below.

## Charter / plan file note (read first)

The work-order RULES line lists the charter as venue_match_service.py + new test
+ STATE (+ config.py), but the plan it orders executed "EXACTLY (exact files …
as written there)" names `backend/app/signals/matching.py` as the file for the
two **required** fixes (Fix 1 weights/entity, Fix 2 date reject). The two
directives conflict; I followed the plan's explicit file assignments (the
work order's primary directive — the required fixes are unimplementable
anywhere else) and kept the diff confined to exactly those plan-named files.
No migrations, no other files touched, no secrets, no push/deploy, explicit
`git add` of charter files only.

## Changes

### Fix 2 (required) — date hard-reject softened for placeholder ends
`backend/app/signals/matching.py`

Plan option B (A's literal "within N days of now" window breaks
`test_g02_hard_reject_via_match_resolution_terms`, whose fixed 2026-01-15/17
dates rot out of any now-relative window — that test is outside charter and
must stay green). As implemented, per the plan's B text:

- Hard-reject (`resolution_date_reject`, conf 0.0) iff calendar days differ
  **and** day-delta > `DATE_REJECT_MAX_DAY_DELTA = 1` **and** both timestamps
  are "sharp".
- "Sharp" = not a venue placeholder end: Kalshi New-Year midnights
  (YYYY-01-01 00:00:00) and Polymarket year-ends (Dec 31 23:59) are
  placeholders (`_is_placeholder_end`); they carry no resolution signal, so a
  disagreement involving one soft-passes with a diagnostic
  `resolution_date_soft_pass(day_delta=N)` reason and simply forfeits the
  close-time sub-score.
- Adjacent-day (delta=1) pairs also soft-pass (cross-midnight same-event
  timestamps); `close_tolerance` (1h) still gates the close-time credit.
- Floors kept: fp-01 (2d, sharp) and fp-04 (91d, sharp) still hard-reject;
  the G02 unit-test pair (2d, sharp) still hard-rejects; the rule is
  pairwise (time-independent) so the fixed-date tests never rot.

Also: naive datetimes are normalized as UTC (`_as_utc`) — SQLite test DBs
drop tzinfo and `astimezone` on naive values would reinterpret them as
machine-local time, which shifted placeholder signatures in-test.

### Fix 1 (required) — 0.75/0.50 reachable without synthetic shared event_id
`backend/app/signals/matching.py` + `venue_match_service.py`

Took the plan's "keep weights but set catalog min_confidence to 0.50 for
persist only" branch for event_id (its rebalance-to-0.20 suggestion breaks
`test_arb_matching.py::test_event_id_match_alone_gives_high_confidence`, which
pins event_id ≥ 0.40 and is outside charter), with the plan's entity redesign:

- Entity sub-score = **entity Jaccard**, not full-set equality (plan values):
  `j ≥ 0.80` → `entity_match` **0.40** (weight raised 0.35→0.40);
  `0.50 ≤ j < 0.80` → `entity_partial(jaccard=…)` **0.20**; else
  `entity_mismatch` 0 (floor: one shared generic word can never confirm).
- Person/team rule (plan item 3): Kalshi "Event: Candidate" colon form — the
  right-hand candidate name (≥ `MIN_CANDIDATE_NAME_TOKENS = 2` tokens; a
  1-token RHS like "Anthropic" is brand overlap, not a person match) fully
  contained in the other side's tokens → full entity credit
  (`entity_person_name_match`), checked symmetrically.
- Title sub-score: full 0.15 (Jaccard ≥ 0.50, raised from 0.10), partial 0.05
  (≥ 0.25). event_id 0.40 and close_time 0.15 unchanged.
- `VenueMatchService.match_open_catalog` default `min_confidence` 0.75 →
  **0.50**, persist-only: `match_and_persist` and `match_venue_markets`
  defaults stay 0.75 (G02 gate untouched). `venue_gap_task` passes no
  min_confidence, so prod persists at 0.50 without touching tasks.py.
- Resulting floors at the 0.50 persist gate: title-only maxes at 0.15;
  entity_partial+anything-but-full-title ≤ 0.35; persisting requires
  full entity (person/Jaccard≥0.80) + a full title match (0.55) or a
  same-hour close (0.55), or a shared event id + any second signal. Every
  persisted row still carries `confidence` + `stale` for downstream gating.

Acceptance met: diagnosis A1 (Ben-Gvir), A2 (Golan), A3 (Levin) production
phrasing, venue-native non-equal external ids, locks 2026-12-31T23:59 vs
2045-01-01T00:00 → **0.55, confirmed at 0.50** (was 0.00; 0.10 with the date
reject bypassed).

### Fix 3 (required) — catalog scan reaches the counterparts, stops being silent
`backend/app/services/venue_match_service.py` + `backend/app/core/config.py`

- `VENUE_GAP_MATCH_LIMIT` default 200 → **500** (plan range 500–1000; the
  Israel-PM PM market sat at rank ~348 by lock_at, and open KS count is <500,
  so 500 covers both; `venue_gap_task`/`venue_gap_service` already read this
  setting — no tasks.py edit needed).
- Cheap prefilter (plan item 2): pairs sharing no non-stop-word token of
  length ≥ 4 (`titles_share_content_token`) are skipped before scoring —
  keeps the 500×500 pass cheap.
- Per-pass stats (plan item 3): `pm_scanned, ks_scanned, pairs_scored,
  pairs_skipped_prefilter, max_confidence, date_rejects, below_threshold,
  matched` — logged at INFO each pass and exposed as
  `service.last_scan_stats`, so prod shows `max_confidence > 0` even before
  persist instead of a silent `matched=0`.
- Kept the plan's single-window "raise the limit" option (not dual-window):
  500 covers both ranks named in the diagnosis and stays one query per venue.

### Fix 4 — no change needed
Plan scopes it "only if Fix 1 still needs a bridge". Fix 1 makes the persist
floor reachable without cross-venue event_id equality, so event_id stays
bonus-only and the ingest connectors / `Market.external_id` writers were not
touched (out of charter regardless).

### Fix 5 — tests
Per the work order, all new tests live in `backend/tests/test_loop112_matcher.py`
(20 tests). Existing test files/fixtures untouched (charter); they stay green
(see regression below). Coverage:

- A1/A2/A3 production phrasing → confirmed ≥ 0.50 (would-fail-before: 0.00).
- Entity partial tier: diagnosis A1 curated sets (j=0.55) → exactly +0.20
  (would-fail-before: entity_mismatch, +0.0); tier boundaries 0.80/0.50 pinned.
- Person-name rule fires for multi-token candidates; 1-token RHS floor pinned.
- Placeholder soft-pass + adjacent-day soft-pass (would-fail-before: hard 0.0).
- Clearly-different pairs must NOT match: Anthropic ticker vs OpenAI IPO
  (diag set B) and SpaceX mkt-cap vs Mars landing → unconfirmed, conf 0.0.
- Floors: sharp 2-day and 91-day date mismatches still hard-reject; canonical
  shared-event Lakers/Celtics still confirms at the strict 0.75 gate.
- Persist-only thresholds pinned (catalog 0.50 / direct 0.75), config default
  pinned (500), prefilter unit tests, and two DB-backed `match_open_catalog`
  tests asserting persisted row (confidence + stale=False + reasons) and the
  full stats dict (incl. `date_rejects` counting and `max_confidence > 0`).

## VERIFY (verbatim, charter command)

```
$ cd backend && uv run --extra dev pytest -q tests/test_loop112_matcher.py tests/test_loop111_wiring.py --basetemp=E:/polymarket-worktrees/loop112-matcher/.pt ; uv run --extra dev ruff check app tests
.............................                                            [100%]
29 passed in 7.52s
All checks passed!
```

## Regression (outside charter verify; must stay green — "G02 false-positive
date tests still green", "no paper-trading guardrail regressions")

```
$ uv run --extra dev pytest -q tests/test_arb_g02_matcher.py tests/test_arb_matching.py tests/test_phase1_signals_core.py tests/test_arb_service.py --basetemp=E:/polymarket-worktrees/loop112-matcher/.pt
...................................................                      [100%]
51 passed in 8.70s

$ uv run --extra dev pytest -q tests/test_arb_*.py tests/test_paper_signals.py tests/test_phase1_signals_core.py tests/test_venue_adapters.py tests/test_weather_signals.py --basetemp=E:/polymarket-worktrees/loop112-matcher/.pt
...................................................                      [100%]
51 passed in 7.97s

$ uv run --extra dev pytest -q tests/test_screener_endpoint.py --basetemp=E:/polymarket-worktrees/loop112-matcher/.pt   # signals_service consumer
......                                                                   [100%]
6 passed in 8.05s
```

G02 benchmark: ≥16/20 true positives at 0.75, **0 false positives**; the two
labeled date-mismatch negatives (fp-01, fp-04) still hard-reject. Baseline
before this change: same files 39 passed.

## Not done / deploy

- Deploy + prod `matched > 0` observation (plan's "Done when" items 1–2) is
  out of charter: no push/deploy from this worktree. On deploy, watch
  `venue_gap_task` summary `matched` and the new `venue match pass: {...}`
  INFO log line.
- Known residual (documented, not fixed — out of charter): PM open catalog is
  599 rows, so ranks 501+ by soonest lock still fall outside the scan; the
  plan's dual-window is the follow-up if prod needs it.

## AutoLab

AutoLab: baseline=39 passed (g02+arb+phase1+loop111 gates, verified pre-edit) | benchmark=`uv run --extra dev pytest -q tests/test_loop112_matcher.py tests/test_loop111_wiring.py` + ruff | iterations=1 (20/29 + ruff clean, regression 51+51+6 green) | budget=n/a | outcome=improved
