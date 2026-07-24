# PREDEPLOY104 — Merged-tree pre-deploy verification

**Repo:** `E:/polymarket-worktrees/_integration`  
**Role:** pre-deploy verifier (read-only; no source edits, push, or deploy)  
**Date:** 2026-07-24  
**Scope:** merged integration of social/community backend + migration 065, traders/library routes, community stories UI  

## VERDICT: SAFE TO DEPLOY

Hard blockers (checks **1, 3, 5, 6**) all **PASS**.  
Check **2** is **UNVERIFIED** (no authenticated local scratch DB; Docker daemon down) — non-blocking under stated rules, but migration apply/reverse was **not** exercised against a live database.

---

## Check results

| # | Check | Result | Command → real output (summary) |
|---|--------|--------|----------------------------------|
| 1 | Single alembic head + 065 chains on 064 | **PASS** | See below |
| 2 | Migration upgrade / downgrade / upgrade | **UNVERIFIED: no scratch DB** | See below |
| 3 | Full backend suite on merged tree | **PASS** | `2092 passed, 28 skipped in 620.94s (0:10:20)` |
| 4 | Ruff lint | **PASS** | `All checks passed!` |
| 5 | OpenAPI snapshot (merged tree) | **PASS** | `3 passed in 47.79s` |
| 6 | Authz matrix (merged tree) | **PASS** | `2 passed in 74.21s (0:01:14)` |
| 7 | Frontend typecheck + lint + build | **PASS** | All exit 0; see tails below |
| 8 | Route collision sanity | **PASS** | Target routes appear exactly once each |

---

### 1. Single alembic head

**Command:**
```text
cd backend && uv run alembic heads
uv run alembic history | (first 20 lines)
```

**Real output:**
```text
065_social_community (head)
---
064_alpha_runs -> 065_social_community (head), social community: comments, reactions, watchlist shares
063_marketplace_ratings -> 064_alpha_runs, persist multi-factor alpha research runs
062_notif_engagement -> 063_marketplace_ratings, marketplace ratings + is_featured flags
061_scanner_test_runs -> 062_notif_engagement, Loop V90 N1: engagement notifications schema
060_scanner_versions -> 061_scanner_test_runs, flag scanner runs executed in pre-publish test mode
059_community -> 060_scanner_versions, add scanner_versions history table
058_scanners -> 059_community, add community subscriptions table
057_skills -> 058_scanners, add scanners and scanner_runs tables
056_terminal_sessions -> 057_skills, add skills library registry
055_live_forecast_lock -> 056_terminal_sessions, add terminal research sessions
054_sentiment_trend -> 055_live_forecast_lock, require a lock timestamp for live forecasts
053_pods -> 054_sentiment_trend, persist market sentiment snapshots (Loop V61 S2).
052_heartbeat -> 053_pods, pod strategy tables (Loop V57 P1).
051_venue_gaps -> 052_heartbeat, Loop V59 H2: heartbeat decision_log table (revision id <= 32 chars).
050_whale_flow -> 051_venue_gaps, cross-venue implied probability gaps (Loop V58 D2)
048_lock_provenance -> 050_whale_flow, whale flow events table (Loop V58 D1)
047_social -> 048_lock_provenance, per-lock forecast provenance (Loop V56 P1)
046_notifications -> 047_social, public trader profiles and follow relationships (Loop V22 S1/S2)
045_admin_cancel_suspend -> 046_notifications, Loop V24 N1: per-user in-app notifications table
043_signal_events_created_idx -> 045_admin_cancel_suspend, Loop V23: market_status cancelled + users.is_suspended
```

**PASS:** Exactly **one** head (`065_social_community`). Chain is linear: `064_alpha_runs -> 065_social_community`. No multi-head merge defect.

---

### 2. Migration applies AND reverses (scratch/local only)

**Attempted environment:**
- No `backend/.env` or root `.env` in the worktree.
- `DATABASE_URL` not set in shell.
- Docker daemon **not** running (`dockerDesktopLinuxEngine` pipe missing).
- `localhost:5432` is open, but compose default credentials failed:

```text
connection to server at "localhost" (::1), port 5432 failed: FATAL:  password authentication failed for user "alphaedge"
```

**Not run (by policy):** `alembic upgrade head` / `downgrade -1` against production or any unknown remote DSN.

**Result:** `UNVERIFIED: no scratch DB`

---

### 3. Full backend suite on the merged tree

**Command:**
```text
cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/_integration/.ptpre
```

**Real summary line:**
```text
2092 passed, 28 skipped in 620.94s (0:10:20)
```

**Exit code:** 0  

**PASS:** No failures. Full suite completed (~10m20s). No merge-only test breakage observed.

---

### 4. Lint

**Command:**
```text
cd backend && uv run --extra dev ruff check app tests
```

**Real output:**
```text
All checks passed!
```

**Exit code:** 0 — **PASS**

---

### 5. OpenAPI snapshot current on MERGED tree

**Command:**
```text
cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py
```

**Real output:**
```text
...                                                                      [100%]
3 passed in 47.79s
```

**Exit code:** 0 — **PASS**  
No path-set drift between merged OpenAPI and committed snapshot.

---

### 6. Authz matrix on the merged tree

**Command:**
```text
cd backend && uv run --extra dev pytest -q tests/test_loop26_authz_matrix.py
```

**Real output:**
```text
..                                                                       [100%]
2 passed in 74.21s (0:01:14)
```

**Exit code:** 0 — **PASS**  
No expected-vs-actual count drift from independently bumped hardcoded counts. Collision between social and traders/library authz count edits did **not** surface.

---

### 7. Frontend gate

#### 7a. typecheck

**Command:** `cd frontend && npm run typecheck`

**Real output (tail):**
```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

**Exit code:** 0 — **PASS** (no type errors printed)

#### 7b. lint

**Command:** `cd frontend && npm run lint`

**Real output (tail):**
```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

**Exit code:** 0 — **PASS**

#### 7c. build

**Command:** `cd frontend && npm run build`

**Real output (tail / route table excerpt):**
```text
> alphaedge-frontend@0.1.0 build
> next build

▲ Next.js 15.5.18
✓ Compiled successfully in 29.6s
✓ Generating static pages (119/119)

Route (app)                                         Size  First Load JS
...
○ /community                                   7.06 kB         122 kB
...
○ /library                                     7.92 kB         123 kB
...
○ /traders                                     5.31 kB         121 kB
ƒ /traders/[name]                              4.61 kB         120 kB
...
● /w/[handle]                                  3.03 kB         118 kB
  └ /w/demo
...
+ First Load JS shared by all                     103 kB
```

**Exit code:** 0 — **PASS**  
Note (non-blocking): build warned that edge runtime disables static generation for that page; telemetry notice present.

---

### 8. Route collision sanity

**Source:** Next.js `Route (app)` table from check 7c build output.

| Route | Occurrences in route table | Status |
|-------|----------------------------|--------|
| `/community` | 1 | OK |
| `/w/[handle]` | 1 | OK |
| `/traders` | 1 | OK |
| `/traders/[name]` | 1 | OK |
| `/library` | 1 | OK |

**Additional:** extracted route paths from the build table showed **no duplicate path tokens** anywhere in the Route (app) listing.

**PASS**

---

## Blockers

**None** among checks 1, 3, 5, 6.

(If policy is later tightened to require check 2 before prod migrate: migration apply/reverse remains **UNVERIFIED** — see Risks.)

---

## Risks worth knowing before deploy (non-blocking)

1. **Migration reverse not exercised on a DB.** Linear single head is confirmed from files, and the full pytest suite passed, but live `upgrade head` → `downgrade -1` → `upgrade head` was not run. Docker was down; localhost:5432 rejected compose-default `alphaedge` credentials. Recommend a one-shot scratch Postgres (compose `db` service) migrate reverse before production migrate.

2. **No worktree `.env`.** Local gate used test defaults / package tooling only. Production migrate path still needs a deliberate, non-prod-first runbook with a known scratch DSN.

3. **Frontend edge-runtime warning.** Next build reported edge runtime disabling static generation for at least one page. Existing product choice; not a merge defect.

4. **Deploy/prod smoke not in this gate.** This report is **merged-tree CI-style verification only**. Per project rules, deploy-affecting work still needs `py -3.13 scripts/verify_prod.py` against production (and `orchestration/gate.py` if that is the org ship bar) — not executed here (would touch shared/prod surfaces; out of this verifier’s write/deploy ban).

5. **Skipped tests:** 28 skipped in the full suite. Normal for environment-gated tests; no failures.

---

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot pre-deploy verification.

---

## Paste-ready evidence block

```text
#1 alembic heads
065_social_community (head)
064_alpha_runs -> 065_social_community (head)

#2 migration reverse
UNVERIFIED: no scratch DB
(docker daemon down; localhost:5432 password auth failed for user alphaedge)

#3 full pytest
2092 passed, 28 skipped in 620.94s (0:10:20)

#4 ruff
All checks passed!

#5 openapi snapshot
3 passed in 47.79s

#6 authz matrix
2 passed in 74.21s (0:01:14)

#7 frontend
typecheck exit 0 | lint exit 0 | build exit 0 (Next.js 15.5.18, 119 static pages)

#8 routes once each
/community=1 /library=1 /traders=1 /traders/[name]=1 /w/[handle]=1
```

**Final: SAFE TO DEPLOY** (with migration reverse still unverified on a live scratch DB).
