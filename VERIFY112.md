# VERIFY112 — three post-deploy anomalies (READ-ONLY)

**Role:** Diagnostician (paper SIM only)  
**Repo:** `E:/polymarket-worktrees/_integration`  
**Prod API:** `https://alphaedge-api-production-b9db.up.railway.app`  
**Sample time (UTC):** 2026-07-26 ~03:20–03:25  
**Constraints:** no source edits, no push/deploy, no secret values (Railway: key presence only)

---

## Prod fingerprint (what is actually running)

| Probe | Result |
|--------|--------|
| `GET /api/v1/system/loops` | Process heartbeats continuous since **2026-07-25T12:50:32Z** (~14.5h uptime at sample) |
| Loop registry keys on prod | **Missing** `model_retrain`, `nightly_backtest`, `market_snapshots`, `order_expiry` |
| Same keys in repo after loop112 dual-wire (`a8ee169+`) | **Present** in `LOOP_INTERVALS` |
| Pre-loop112 parent of `83bc644` | Also missing those four keys |
| Railway CLI status | Service Online; latest attempt **Deploy failed** (~16m before sample); prior image still serving |
| Railway variables | **No** `SCHEDULER_WHALE_REFRESH_ENABLED`, **no** `SCHEDULER_GENERIC_ARTIFACT_RETRAIN_ENABLED`, **no** `VENUE_GAP_MATCH_LIMIT` (or other `VENUE_GAP_*` / scheduler retrain keys). `PAPER_TRADING_ONLY` present. |
| Railway logs (JSON scan, ~1.3k lines; filters whale / generic_artifact / boot catch-up / venue match) | **0 hits** for those strings |

**Conclusion:** Live prod is **post-loop111, pre-loop112**. The loop112 boot-catch-up + reachable-matcher commits exist in this worktree (`83bc644`…`43857d9`) but are **not** the running process fingerprint.

---

## Anomaly 1 — `whale_refresh` heartbeat `never`

### CAUSE: **other** (sleep-first still live on prod; loop112 boot catch-up not deployed)

Not flag-off. Not a boot catch-up error in logs.

### Evidence

**Repo (fixed code, not live):**

- `backend/app/core/config.py`: `scheduler_whale_refresh_enabled` default **`True`**, alias `SCHEDULER_WHALE_REFRESH_ENABLED`.
- `backend/app/main.py` `_whale_refresh_loop` (current): boot catch-up **first** → `record_heartbeat("whale_refresh", …)` → then `_paced_sleep(604800, …)`.
- Pre-fix parent of `83bc644` (what prod fingerprint matches):

```python
while True:
    await asyncio.sleep(7 * 86400)   # sleep FIRST
    ...
    record_heartbeat("whale_refresh")
```

**Prod:**

| Field | Value |
|--------|--------|
| status | `never` |
| running | `false` |
| last_heartbeat | `null` |
| interval_sec | `604800` |
| detail | `null` |

- Uptime ~14.5h ≪ 7d → under sleep-first, **first heartbeat is impossible yet**.
- Railway var `SCHEDULER_WHALE_REFRESH_ENABLED`: **not set** → code default ON → loop is started, not gated off.
- Logs: no `Whale refresh boot catch-up failed` / no whale_refresh errors (and no success) — consistent with “still sleeping,” not “crashed before heartbeat.”
- Registry fingerprint proves loop112 dual-wire / boot-catch-up is not on this process.

### One-line fix

**Deploy** the loop112 whale boot-catch-up image (`83bc644+`; includes `_whale_refresh_loop` run-then-sleep). No Railway variable required (default is already on). Optional kill-switch name only if you want it off: `SCHEDULER_WHALE_REFRESH_ENABLED`.

---

## Anomaly 2 — `generic_artifact_retrain` heartbeat `never` despite loop112 fix

### CAUSE: **other** (same as #1: sleep-first still live; loop112 catch-up not on prod)

Not flag-off. **Not a first-run bug** in the fixed code.

### Evidence

**Fixed loop (repo `437ea68+`, not live):**

```text
boot:
  if _has_generic_artifact_retrain_this_week():  # count ModelVersion for MODEL_NAME in last 7d
      heartbeat detail=skipped:retrain_exists_this_week
  else:
      run generic_artifact_retrain_task → heartbeat
then weekly _paced_sleep(604800)
```

- `_has_generic_artifact_retrain_this_week`: `return bool(count and count > 0)`.
- **First-run (no row ever):** `count` is 0/None → `False` → **catch-up runs**. Absence is **not** misread as “already ran.”
- Flag default: `scheduler_generic_artifact_retrain_enabled=True` (`SCHEDULER_GENERIC_ARTIFACT_RETRAIN_ENABLED`).

**Pre-loop112 (prod-aligned):**

```python
while True:
    await _paced_sleep(604800, ...)
    ...
    record_heartbeat("generic_artifact_retrain", ...)
```

**Prod:**

| Field | Value |
|--------|--------|
| status | `never` |
| running | `false` |
| last_heartbeat | `null` |
| interval_sec | `604800` |

- Railway var `SCHEDULER_GENERIC_ARTIFACT_RETRAIN_ENABLED`: **not set** → default ON.
- Logs: no generic_artifact / boot catch-up lines.
- Same pre-loop112 registry fingerprint as anomaly 1.

### One-line fix

**Deploy** loop112 retrain boot-catch-up (`437ea68+`). No first-run code change needed. No Railway variable required. Optional flag name: `SCHEDULER_GENERIC_ARTIFACT_RETRAIN_ENABLED`.

---

## Anomaly 3 — `venue_gap` `matched=0` with “new reachable rules”

### CAUSE: **window** (primary on live prod) + **other** (secondary if new rules were live: placeholder detector misses real lock times)

### What is live vs repo

| Knob | Pre-loop112 (live fingerprint) | Repo after matcher (`c89036d` / `43857d9`) |
|------|--------------------------------|-------------------------------------------|
| `VENUE_GAP_MATCH_LIMIT` default | **200** | **500** |
| Catalog `min_confidence` (persist) | **0.75** (`match_and_persist` default; no catalog override) | **0.50** (`match_open_catalog` default) |
| Date disagree | hard `resolution_date_reject` | soft-pass only if placeholder end or dayΔ≤1 |
| Entity | full set equality | Jaccard + person-name rule |
| Railway `VENUE_GAP_MATCH_LIMIT` | **not set** | would use code default |

Prod heartbeat (still running every ~60s):

```text
venue_gap status=ok detail="matched=0 upserted=0 skipped_odds=0"
GET /api/v1/venue-gaps?limit=5 → gaps=[], count=0
```

No `venue match pass: {...}` log lines (loop112 matcher observability) → consistent with pre-matcher image.

### Israel-PM pairs vs scan windows (prod catalog, 2026-07-26)

Open catalog: **602** PM + **270** KS with `lock_at`.

| Window | PM cutoff (Nth by soonest `lock_at`) | KS cutoff |
|--------|--------------------------------------|-----------|
| top-**200** (live default) | **2026-10-31** | **2040-01-01** |
| top-**500** (repo default) | **2027-03-31** | all KS (only 270 open) |

Diagnosis person pairs (same human event; A1/A2/A3 class):

| Person | PM slug (rank) | PM lock | KS slug (rank) | KS lock | in top-200 both? | in top-500 both? |
|--------|----------------|---------|----------------|---------|------------------|------------------|
| Ben-Gvir | `pm-will-itamar-ben-gvir-…` **#362** | 2026-12-31T00:00Z | `ks-kxnextisraelpm-45jan01-iben` **#223** | 2045-01-01T15:00Z | **NO** | YES |
| Yair Golan | `pm-will-yair-golan-…` **#355** | 2026-12-31T00:00Z | `ks-kxnextisraelpm-45jan01-ygol` **#218** | 2045-01-01T15:00Z | **NO** | YES |
| Yariv Levin | `pm-will-yariv-levin-…` **#367** | 2026-12-31T00:00Z | `ks-kxnextisraelpm-45jan01-ylev` **#221** | 2045-01-01T15:00Z | **NO** | YES |

**Live (limit 200): window, not rules.** The matcher never pairs them because PM ranks ~352–367 and KS ranks ~218–223 are **outside** the top-200-by-`lock_at` scan on **both** venues.

### If new reachable rules *were* live (counterfactual on current lock times)

Repo scoring with **actual prod timestamps** (not the idealized 23:59 / 00:00 used in STATE112 acceptance):

| Input | Result |
|--------|--------|
| PM `2026-12-31T00:00:00Z`, KS `2045-01-01T15:00:00Z` | `confidence=0.0`, reasons=`('resolution_date_reject',)` |
| Idealized PM `…T23:59`, KS `…T00:00` | `confidence=0.55`, `confirmed` at min 0.50 |

Why: `_is_placeholder_end` only treats:

- Jan 1 **00:00:00** (Kalshi New-Year midnight), or  
- Dec 31 **23:59** (Polymarket year-end)

Prod Israel-PM locks are **Dec 31 00:00** and **Jan 1 15:00** → both “sharp” → dayΔ ≫ 1 → hard zero **even after** window raise to 500.

So: under true live code → **window**. Under deployed-repo rules with real data → still **rules/placeholder-shape mismatch**, not “already fixed.”

### One-line fix

1. **Deploy** loop112 matcher + raise (`VENUE_GAP_MATCH_LIMIT` default 500 already in repo; or set Railway name `VENUE_GAP_MATCH_LIMIT` if you keep an old default).  
2. **Code bug (if after deploy still 0):** widen `_is_placeholder_end` to treat calendar **Jan 1** / **Dec 31** (any hour) or far-horizon year locks as placeholders so prod `…T00:00` / `…T15:00` soft-pass like the diagnosis fixtures.

---

## Summary table

| # | Loop / signal | CAUSE | Flag default / Railway name | Live blocker |
|---|---------------|--------|------------------------------|--------------|
| 1 | `whale_refresh` | **other** (sleep-first; loop112 not live) | default ON; var **unset** (`SCHEDULER_WHALE_REFRESH_ENABLED`) | 7d sleep before first HB |
| 2 | `generic_artifact_retrain` | **other** (same; **not** first-run bug) | default ON; var **unset** (`SCHEDULER_GENERIC_ARTIFACT_RETRAIN_ENABLED`) | 7d sleep before first HB |
| 3 | `venue_gap` matched=0 | **window** (live limit 200); **other** residual if new rules + real locks | `VENUE_GAP_MATCH_LIMIT` **unset** → live default 200 | Israel-PM outside top-200 both venues; placeholder hour mismatch under new rules |

---

## AutoLab

AutoLab: not applicable (read-only diagnosis; no iterative measure)

---

## STOP

No source edits beyond this file. No push/deploy. No secret values printed. Temp Railway JSON dump and market rank script deleted after use.
