# MATCHER-DIAG112 — Venue matcher `matched=0` for 13+ hours

**Role:** Diagnostician (READ-ONLY)  
**Date:** 2026-07-25 / 2026-07-26 (UTC sample window)  
**Repo:** `E:/polymarket-worktrees/_integration`  
**Prod API (GET only):** `https://alphaedge-api-production-b9db.up.railway.app`  
**Question:** Venue matcher runs every 60s with `matched=0` for 13+ hours. Honest no-overlap, or too-strict matching?

---

## VERDICT

**(b) + (c) — overlap exists but rules block it; structural catalog/scan issues amplify zeros.**

Not pure (a). A human would match several same-person / same-topic pairs (especially next Israeli PM). Every such pair is killed before threshold by hard date reject and/or never reaches 0.75 because production scoring cannot hit the weight math without synthetic `event_id` + curated entity sets.

**Primary blockers (ordered):**

1. **Hard `resolution_date_reject`** when both `lock_at` UTC calendar days differ → confidence forced to **0.0**.
2. **`min_confidence=0.75` weight math** requires **both** `event_id_match` (0.40) **and** `entity_match` (0.35) in practice; without shared `event_id`, theoretical max is **0.60**.
3. **Entity rule is full set equality** of *all* title tokens (default when no curated entities). Near-identical person markets still `entity_mismatch`.
4. **`catalog_limit=200`** (soonest `lock_at` per venue) compares PM near-term sports/crypto vs KS medium/long-dated markets; the best human pairs sit **outside** the PM top-200 window.
5. **Catalog composition** is mostly non-overlapping themes (PM-only Fed/BTC/NBA; KS-only Pope/Mars/GDP long-dated). That is real partial (a), but not the whole story.

Prod confirmation: `GET /api/v1/venue-gaps?limit=5` → `"gaps":[],"count":0` (consistent with empty match table).

---

## Method

1. Read `backend/app/services/venue_match_service.py` and `backend/app/signals/matching.py`.
2. Trace production caller: `venue_gap_task` → `match_open_catalog(max_pairs=match_limit, catalog_limit=match_limit)` every 60s (`VENUE_GAP_*`).
3. Sample prod `GET /api/v1/markets?limit=200` with offsets until exhaust (1722 markets).
4. Classify open markets by `source` / slug prefix.
5. Find human same-event candidates; score with real `match_venue_markets`.
6. Simulate catalog_limit=200 scan; score near-misses with/without date hard-reject.

No source edits. No secrets. No push/deploy.

---

## Matching logic (what the code actually does)

### Call path

| Piece | Behavior |
|--------|----------|
| Loop | `_venue_gap_loop` / ARQ cron → `venue_gap_task` every ~60s |
| Matcher | `VenueMatchService.match_open_catalog` |
| Defaults | `min_confidence=0.75`, `max_pairs=200`, `catalog_limit=200` (`VENUE_GAP_MATCH_LIMIT`) |
| Catalog query | `status=OPEN`, `source in {polymarket,kalshi}`, slug prefix `pm-` / `ks-`, ordered by `lock_at ASC`, limit N |
| Pairing | Greedy: for each PM, best KS with conf ≥ min; persist those |

Slug / source filters are **not** broken: open catalog has `pm-` + `ks-` rows correctly.

### Score model (`match_resolution_terms` / `match_venue_markets`)

| Sub-score | Weight | Rule |
|-----------|--------|------|
| `event_id_match` | 0.40 | Normalized string equality of `external_id` |
| `entity_match` | 0.35 | **Exact set equality** of entity tokens |
| `close_time_match` | 0.15 | Abs delta ≤ 1 hour |
| `title_token_match` | 0.10 / 0.05 | Jaccard ≥ 0.50 → +0.10; ≥ 0.25 → +0.05 |

**Hard reject (G02):** if both sides have `close_at` and UTC **calendar dates differ** → `confidence=0.0`, reason `resolution_date_reject`. No further scoring.

**Default entities in production path:** when `pm_entities` / `ks_entities` are not supplied (they are not in `match_open_catalog`), entities = **all content tokens of the title** (stop-words stripped). That makes set equality nearly impossible across venues' different phrasing.

**Confirm threshold:** `status=confirmed` iff `confidence >= min_confidence` (0.75).

### Weight math (why 0.75 is unreachable on real catalogs)

```
without event_id:  max = 0.35 + 0.15 + 0.10 = 0.60  < 0.75
event_id + close + title (no entity): 0.40 + 0.15 + 0.10 = 0.65  < 0.75
event_id + entity: 0.40 + 0.35 = 0.75  ✓  (minimum path)
```

G02 fixture pairs (`tests/fixtures/arb/match_pairs_20.json`) always inject **identical** `pm_event_id`/`ks_event_id` and **curated equal entity lists**. Production DB `external_id` values are venue-native (Polymarket condition ids vs Kalshi tickers) and almost never equal. So the only path the fixture uses to clear 0.75 **does not exist** on live data.

---

## Prod catalog sample (GET /api/v1/markets)

| Metric | Value |
|--------|------:|
| Total fetched | 1722 |
| Open | 884 |
| Locked | 90 |
| Resolved | 748 |
| Open polymarket (`pm-`) | 599 |
| Open kalshi (`ks-`) | 270 |
| Open seed/other | 15 |

Open category mix (both venues): Politics, Sports, Tech, Economics, Crypto, Culture, NBA, Weather, …

### Lock-date shape (root of date rejects + catalog window)

| Venue | Open lock-day range | Top lock days |
|-------|---------------------|---------------|
| PM | 2026-07-25 → 2028-11-07 | 2026-12-31 (138), 2026-10-31 (73), 2026-07-31 (56) |
| KS | 2026-09-30 → 2099-08-01 | 2045-01-01 (31), 2031-01-01 (23), 2035-01-01 (21) |

**Shared UTC lock calendar days between open PM and open KS: only 4**  
`2026-09-30`, `2027-01-01`, `2027-07-01`, `2028-01-01`.

On those 4 days: **165** same-day PM×KS pairs; **0** with title Jaccard ≥ 0.15. Examples are unrelated (e.g. Russian election / aliens vs NFL retirement; NBA champ vs TV release date).

### `catalog_limit=200` window (what the loop actually scores)

| | Soonest lock in top-200 | Cutoff (200th) |
|--|-------------------------|----------------|
| PM | 2026-07-25 (MLS/soccer game days, BTC daily, tweet counts) | 2026-10-31 |
| KS | 2026-09-30 (NFL retirement, TV release, FDA, …) | ~2040-01-01 |

Simulated 200×200 best-per-PM: **max confidence = 0.0** — every pair hit `resolution_date_reject`.

---

## Theme overlap (honest partial (a))

| Theme | Open PM | Open KS | Human same-event? |
|-------|--------:|--------:|-------------------|
| Fed / rates July | 33 | 0 | No KS market |
| US presidential / nominee 2028 | 25 | 0 | No KS market |
| Bitcoin | 31 | 0 | No KS market |
| NBA | 70 | 0 | No KS market |
| F1 | 22 | 0 | No KS market |
| Iran / Taiwan / Putin | yes | 0 | PM-only |
| Pope | 0 | 7 | KS-only |
| Mars / Elon lifetime | 0 | yes | KS-only |
| Climate goals | 0 | 4 | KS-only |
| GDP long-dated | 0 | 16 | KS-only |
| **Next Israeli PM (person markets)** | **7+** | **8** | **YES — same people** |
| OpenAI / Anthropic (name only) | 14 | 2 | **Related brands, different questions** (best model / acquire vs IPO first) |
| SpaceX (name only) | 2 | 1 | Different questions (mkt cap vs Mars landing) |

**Conclusion on (a):** Large slices of each catalog have **no** counterpart. That alone would keep match counts low. It does **not** explain zero matches given clear Israel-PM person pairs.

---

## Human same-event near-misses (exact pairs + which rule blocked)

### Pair set A — Next Israeli PM (same person both venues)

These are the strongest human matches in the open catalog.

| # | PM title (abbrev) | KS title (abbrev) | PM lock | KS lock | Title Jaccard | Prod conf | Blocking rule(s) |
|---|-------------------|-------------------|---------|---------|---------------|-----------|------------------|
| A1 | Will **Itamar Ben Gvir** be the next Prime Minister of Israel? | Who will succeed Netanyahu as Prime Minister of Israel?: **Itamar Ben-Gvir** | 2026-12-31 | 2045-01-01 | **0.55** | **0.00** | (1) `resolution_date_reject` (days differ) |
| A2 | … next PM of Israel … **Yair Golan** | … succeed Netanyahu …: **Yair Golan** | 2026-12-31 | 2045-01-01 | **0.50** | **0.00** | same date reject |
| A3 | … next PM of Israel … **Yariv Levin** | … succeed Netanyahu …: **Yariv Levin** | 2026-12-31 | 2045-01-01 | **0.50** | **0.00** | same date reject |

**If date hard-reject is bypassed** (close times omitted — diagnostic only):

| Pair | Conf | Reasons (abbreviated) | Why still << 0.75 |
|------|------|------------------------|-------------------|
| A1 | **0.10** | `event_id_missing`, `entity_mismatch`, `close_time_missing`, `title_token_match(jaccard=0.55)` | Title full credit only (+0.10). Entity sets unequal: PM `{ben,gvir,israel,itamar,minister,next,prime}` vs KS `{as,ben,gvir,israel,itamar,minister,netanyahu,prime,succeed,who}`. No event_id. |
| A2 | **0.10** | same pattern, jaccard=0.50 | Same structural fails |
| A3 | **0.10** | same pattern, jaccard=0.50 | Same structural fails |

**Threshold gap:** computed soft score **0.10** vs required **0.75** (gap **0.65**).  
Even with perfect entity equality + same-hour close (impossible under current entity definition without curated lists): max without event_id = **0.60** still below 0.75.

**Catalog window:** first Israel-PM PM market sits at **rank ~348** by `lock_at` (lock 2026-12-31) → **outside** `catalog_limit=200` (cutoff 2026-10-31). KS Israel PM at 2045 is near/after the KS top-200 edge. So the loop often **never scores these pairs at all**.

### Pair set B — Brand-name overlap, not same event (controls)

| PM | KS | Jaccard | Conf | Block |
|----|----|---------|------|-------|
| Will Anthropic's public ticker be $ANTH? / best AI model July | Will OpenAI or Anthropic IPO first?: Anthropic | ~0.14 | 0.00 | Date reject; also not same resolution question |
| SpaceX largest mkt cap Dec 31 | SpaceX land on Mars before 2030 | ~0.08 | 0.00 | Date reject; different event |
| Elon tweet counts July 2026 | Time's Person of the Decade: Elon Musk | ~0.20 | 0.00 | Date reject; different event |

These should **not** match. Date reject correctly zeros them; they are not evidence of over-strictness alone.

### Pair set C — Same calendar day only

165 open same-day pairs; **0** with Jaccard ≥ 0.15. No hidden same-event gold under shared lock days in this snapshot.

---

## Structural issues (verdict c)

| Issue | Evidence | Effect |
|-------|----------|--------|
| Cross-venue `external_id` never shared | Matcher uses `Market.external_id`; fixtures invent shared IDs; live PM vs KS IDs are different systems | `event_id_match` never fires → cannot reach 0.75 |
| Entity = full title token set | `match_venue_markets` defaults entities from `_title_tokens(title)` | `entity_match` almost never true across venues |
| `lock_at` treated as resolution day | Hard reject on calendar day | Venue placeholder ends (e.g. KS 2045-01-01) kill real topical pairs |
| `catalog_limit=200` by soonest lock | PM window is short-dated games; KS window starts later and is long-dated | Best human pairs not in Cartesian product |
| Theme inventory skew | Open PM heavy near-term politics/sports/crypto; open KS heavy long-horizon | Many true “no counterpart” markets (partial a) |
| Slug/source filters | `pm-`/`ks-` and sources look correct | **Not** the bug |

Slug format mismatch is **not** the root cause. Field semantics for **close/resolution time** and **event id** are.

---

## Why `matched=0` every 60s is expected under current code

```
every 60s:
  load ≤200 open pm- by soonest lock_at
  load ≤200 open ks- by soonest lock_at
  for each pm×ks:
      if lock days differ → conf=0
      else score ≤0.60 without shared event_id
      keep only conf ≥ 0.75
  → matched = 0
```

Prod `venue-gaps` empty is the downstream symptom of an empty `venue_market_matches` table, not a separate gap bug.

---

## Junior-implementable fix plan

Scope only matcher/catalog so real same-event pairs can confirm without weakening paper-trading guardrails. Keep G02 “0 false positives on date-mismatched labeled negatives” intent, but stop using venue placeholder years as fatal.

### Fix 1 — Make 0.75 reachable without synthetic shared event_id (required)

**File:** `backend/app/signals/matching.py`

1. Change entity sub-score from boolean set equality to **entity Jaccard**:
   - `j >= 0.80` → full 0.35 (`entity_match`)
   - `0.50 <= j < 0.80` → partial e.g. 0.20 (`entity_partial`)
   - else mismatch / 0
2. Rebalance weights so **entity_partial + close_time + title** or **entity_match + title** can confirm without event_id, e.g.:
   - entity 0.40, title 0.25, close_time 0.15, event_id 0.20  
   - OR keep weights but set catalog `min_confidence` to **0.50** for persist only (gap loop already uses `venue_gap_min_confidence=0.5` for gaps)
3. Prefer **person/team token intersection** for multi-outcome titles (`Event: Candidate` Kalshi form): extract right-hand candidate name; require that proper-name set intersects.

**Acceptance:** A1 Ben-Gvir pair with close times cleared or same-day soft window scores **≥ 0.75** (or ≥ chosen persist threshold) and status confirmed.

### Fix 2 — Soften date hard-reject for long-horizon placeholders (required for Israel-PM class)

**File:** `backend/app/signals/matching.py`

Options (pick one; junior-safe is A):

- **A (recommended):** Hard-reject only when **both** locks are within N days of now (e.g. 90d) **and** calendar days differ. Far-future / multi-year placeholder ends do not hard-zero; they only omit `close_time_match`.
- **B:** Hard-reject only if day delta > D (e.g. 7 or 30) **and** both times are “sharp” (not year-granularity midnights).
- **C:** Do not pass `lock_at` as `close_at` for matching; use a dedicated resolution-date field when present.

**Keep** labeled G02 false-positive date tests by adjusting fixtures to near-term same-event vs different-day cases, not 2026-vs-2045 placeholders.

**Acceptance:** A1–A3 no longer return conf 0 solely from 2026-12-31 vs 2045-01-01; soft score path runs.

### Fix 3 — Catalog scan must include thematic counterparts (required)

**File:** `backend/app/services/venue_match_service.py` (+ config)

1. Raise `VENUE_GAP_MATCH_LIMIT` default (e.g. 500–1000) **or** dual-window:
   - Window Near: soonest 150 by `lock_at`
   - Window Wide: top volume / politics+economics open markets up to 150
2. Optional cheap prefilter: only score pairs sharing ≥1 non-stop token of length ≥4 (cuts O(n²)).
3. Log per pass: `pm_scanned`, `ks_scanned`, `pairs_scored`, `max_confidence`, `date_rejects`, `below_threshold` so prod stops being a silent zero.

**Acceptance:** Israel-PM markets appear in scanned sets; heartbeat/detail shows `max_confidence > 0` even before persist.

### Fix 4 — Do not rely on cross-venue event_id equality in prod (data)

**Files:** ingest connectors / `Market.external_id` writers (only if Fix 1 still needs a bridge)

- Either leave event_id as bonus-only, or build a **normalized event key** (sport + teams + date; election + office + person) stored separately from raw venue ids.
- Never expect Polymarket condition id == Kalshi ticker.

### Fix 5 — Tests (must ship with Fix 1–2)

**Files:** `backend/tests/test_arb_matching.py`, `test_arb_g02_matcher.py`, new prod-shaped fixture

Add cases **without** shared event_id:

1. Ben-Gvir / Golan / Levin title pairs (production phrasing) → confirmed under new rules.
2. OpenAI IPO vs “best AI model July” → still unconfirmed (different event).
3. Near-term Lakers vs Celtics same day → still confirmed.
4. Same titles, different near-term resolution days → still hard-reject.
5. Regression: fixture true positives remain ≥16/20; false positives stay 0.

### Explicit non-goals

- No cash / execution / live order path.
- Do not disable `PAPER_TRADING_ONLY`.
- Do not “fix” zeros by hardcoding pairs or lowering threshold to 0.05 without weight redesign (creates false positives).
- Do not change slug prefixes (`pm-`/`ks-`) — they are fine.

### Suggested implement order

1. Fix 2 (date) + unit test — unblocks soft scoring of long-horizon pairs.  
2. Fix 1 (entity Jaccard + weight/threshold) + Israel-PM tests.  
3. Fix 3 (catalog window + diagnostics).  
4. Deploy; watch `venue_gap_task` summary `matched` and `/api/v1/venue-gaps` count.

### Done when

- Prod pass reports `matched > 0` for at least the Israel-PM person pairs (or documented successors).  
- `/api/v1/venue-gaps` non-empty when both venues have prices on a matched pair.  
- G02 false-positive date tests still green.  
- No paper-trading guardrail regressions.

---

## Summary answer

| Option | Applies? |
|--------|----------|
| **(a) Genuinely zero overlap** | **Partially** — most themes are single-venue; not absolute. |
| **(b) Overlap exists; threshold/rules block** | **Yes** — Israel PM person pairs; title Jaccard 0.50–0.55; date reject → 0.00; soft max 0.10; 0.75 unreachable without shared event_id. |
| **(c) Structural** | **Yes** — `lock_at` as resolution day; full-title entity equality; event_id never cross-venue; `catalog_limit=200` soonest-lock window misses the pairs. |

**Root cause in one line:** Production matching is tuned for fixture pairs with shared synthetic event IDs and curated entity lists, then hard-zeros any differing `lock_at` day and only scans 200 soonest markets per venue — so a live catalog with real same-person titles and long Kalshi placeholder dates yields permanent `matched=0`.

---

## AutoLab

AutoLab: not applicable (no iterative measure; diagnostic only, no code change).

## Evidence artifacts (local, not committed required)

- Prod dump used for this note: temporary `_diag112_markets.json` (1722 markets) produced during diagnosis; safe to delete.
- Code anchors:
  - `backend/app/services/venue_match_service.py` (`match_open_catalog`, `_open_by_source`)
  - `backend/app/signals/matching.py` (weights, date reject, entity equality)
  - `backend/app/workers/tasks.py` (`venue_gap_task`, `catalog_limit=match_limit`)
  - `backend/app/core/config.py` (`VENUE_GAP_*` defaults)
  - `backend/tests/fixtures/arb/match_pairs_20.json` (synthetic shared event_ids)
