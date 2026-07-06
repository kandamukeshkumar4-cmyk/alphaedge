# Live-Data Loop — "the deployed demo is genuinely populated and moving" (STATE)

Runner: Claude Opus 4.8 (or stronger). One ticket per iteration. This file is
the loop's memory — update it EVERY iteration before ending the session.
Started 2026-07-06 after the owner opened the DEPLOYED site and found every
screen empty / sample / erroring ("Not Found", "API error", zero-cent flat
charts, no signals). This loop exists to make that never happen again.

## The one-sentence goal (the recursive condition)

A first-time visitor (think: a hiring manager) opens the deployed URL and,
within ~5 seconds, sees a populated, moving, credible product on EVERY core
screen — real markets, price history on the charts, signals in the rails, a
runnable analyst, working CLV / arbitrage / portfolio — with zero raw errors
and zero barren empty states, and with honest labels distinguishing genuinely
LIVE data from seeded/replayed history.

## Why the demo looked broken (root causes found this session — start here)

1. **Frontend fell back to the static origin.** `NEXT_PUBLIC_API_URL` defaulted
   to `""`, so API calls hit the SWA host (no `/api`) → every call failed →
   the UI silently showed sample data. FIXED (frontend now resolves to the
   real backend URL). Ships to prod on the next Azure deploy.
2. **CORS blocked the preview origins.** The backend only trusted the exact
   prod origin + localhost, so the per-PR Azure preview subdomains
   (`…-41.centralus.7.azurestaticapps.net`) were CORS-blocked. FIXED
   (`Settings.cors_origin_regex`). Ships on the next backend deploy.
3. **The deployed backend is serving a STALE/DOWN image.** The HF Space won't
   rebuild to pushed revisions → OWNER must factory-reboot it. Until then the
   live site runs old code no matter what we merge.
4. **OPEN QUESTION this loop must answer (R01): even with a healthy backend, is
   the deployed DB actually populated?** The HF Space runs uvicorn only
   (no ARQ worker, `REDIS_URL=disabled`). The API lifespan starts an in-process
   live-tick loop, but: does a fresh Neon DB ever get seeded? does the tick loop
   survive rate-limits/network? If not, the deploy is empty by construction —
   THIS is the deepest fix and the reason for R01/R02/R06.

## Hard guardrails (violating any = failed iteration, revert)

1. `PAPER_TRADING_ONLY=true` everywhere. No real-money paths, ever.
2. Order path stays `RiskService → OrderIntent → OrderBookService`; no LLM/agent
   order path.
3. **Honest data labeling (the load-bearing guardrail for THIS loop).** Seeded /
   replayed / historical rows may populate every screen, but they must be
   labeled as such (`source=seed`/`replay`, no green "Live" badge). "Live" is
   shown ONLY when a real upstream tick arrived inside the freshness window.
   Making the demo non-empty is NOT license to present sample numbers as live.
4. Never game a benchmark or weaken a test/threshold/gate to go green.
5. No AGPL/commercial code copied — clean-room ideas only.

## The gate (run ALL before marking any ticket DONE)

```bash
cd backend  && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
# Populated-demo smoke against a seeded local stack (offline-safe via fixtures):
cd backend  && DEMO_RICHNESS=1 uv run --extra dev pytest tests/smoke/ -q --base-url http://127.0.0.1:8000
```
Plus for UI tickets: page renders in a browser at desktop/tablet/phone with the
seeded stack — every core screen POPULATED, zero console errors, zero raw
error banners.
Plus for deployed claims: the richness smoke against the real HF Space URL —
ONLY runnable after the owner confirms the Space is rebooted and reachable.

## Verification realism (read before you claim "live-verified")

This dev container CANNOT reach Polymarket / Kalshi / FRED / the HF Space
(proxy-blocked). So:
- Do local verification against a **seeded** Postgres using committed fixtures
  (R02) — this proves every screen populates offline.
- Do NOT claim the DEPLOYED site works until the owner reboots the Space and you
  (or CI) run the richness smoke against its URL. Mark such tickets
  BLOCKED-ON-DEPLOY with the exact command to run, never simulate it.

## Tickets (priority order — top = biggest demo impact)

| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| R01 | **Deployed data-path audit (read-only, gates the rest).** Trace exactly why the live HF Space shows empty: is the Neon DB seeded on first deploy? does the API-lifespan tick loop actually ingest there? does anything need the ARQ worker/Redis that the Space doesn't run? Deliver a findings doc + the minimal fix list feeding R02/R06. Use an explorer subagent; no code yet. | TODO | The single most important ticket — everything else is guesswork until this is answered. |
| R02 | **Rich, honest seed on startup.** A fresh DB must come up with N real markets across categories (NBA/sports/elections/crypto/weather) AND recent price-snapshot history per market (committed fixtures captured from real Polymarket/Kalshi payloads), so feed / markets / charts are never empty. Idempotent; runs in the deploy startup after `alembic upgrade head`. Labeled `source=seed` (NOT Live). | TODO | Benchmark: fresh DB → `/api/v1/markets` ≥ 20, each canonical market has ≥ 30 snapshots → candles render. This is what makes the demo non-barren even before live ingestion warms up. |
| R03 | **Charts show real movement, not "zero cents".** Fix the candles data path end-to-end so every market with snapshots yields a varying candle series, and fix the frontend candle adapter that renders 0/flat. | TODO | Benchmark: seeded market `/candles` returns a series with >1 distinct value; PriceChart renders non-flat at all 5 timeframes. |
| R04 | **Signals / CLV / arbitrage: no raw "API error".** The rails call these endpoints without required params or mishandle empty; make the endpoints return a 200 empty-shape (never 4xx/5xx) when there's no data, fix the frontend calls, and give every rail an honest populated-or-empty state — never a red error banner. | TODO | Repro from the owner's screenshots: pressing Arbitrage/Signals/CLV showed "API error". Benchmark: those surfaces return 200 + render a state on the seeded stack. |
| R05 | **Analyst "Run the analyst now" never dead-ends.** Running the analyst on a visible market must produce a brief or a clear reason — never a bare "Not Found". Ensure the market exists (seed) or create-on-demand from the market source. | TODO | Repro: `pm-us-x-iran-…` → "Run the analyst now" → "Not Found". Benchmark: analyst run on any listed market → 200 brief (fallback generator is fine w/o LLM key). |
| R06 | **Live-feed reliability on the single-process deploy.** Make the in-process tick loop robust on the HF Space (no worker/Redis): backoff, never crash the API, refresh on a schedule; when upstreams are unreachable keep the seed visible + set the honest freshness/label. Consider a tiny cron workflow that pokes an ingest endpoint if in-process proves unreliable. | TODO | Benchmark: API stays up + serves data through simulated upstream failures; "Live" badge only when a real tick landed in-window. |
| R07 | **Populated-demo smoke (richness assertions).** Extend `tests/smoke/` (behind `DEMO_RICHNESS=1`) to assert NON-empty against a `--base-url`: markets ≥ N, ≥ 1 signal, ≥ 1 candle series with variation, CLV/arbitrage/portfolio 200, analyst-run → brief. Runs against seeded local now; against the deployed URL once the Space is up. | TODO | This is the loop's benchmark harness — write it early (right after R02) so R03–R06 have a target. |
| R08 | **Keep deployed data fresh.** If R01 shows live ingestion needs more than the API process, add a minimal always-on refresh (lightweight in-process scheduler, or a GitHub cron that hits a protected ingest endpoint) so the deployed demo keeps moving, not frozen. | TODO | Depends on R01's verdict. Don't over-build — smallest thing that keeps data current on free-tier. |

## Carried from the opus-4.8 loop (still blocked on the owner — not this loop's job)

- **O01** deployed AI live-verify — needs the owner's `NIM_API_KEY`/`LLM_MODEL`
  GitHub secrets + a working HF deploy. (O06 model-routing plumbing is DONE.)
- **O09** LightGBM vs XGBoost A/B — auto-unblocks at ~100 resolved outcomes.
- **O10** FIFA model — needs the owner to supply the CSVs.
- **Design-audit /loop** runs separately and keeps shipping L1/L2 UI polish.

## Iteration protocol (read every run)

1. Read this file + `AGENTS.md` + `goals/build-loop-opus48/STATE.md` (run-1
   history + the demo root-cause record).
2. Pick the FIRST TODO, unblocked ticket (R01 first — it gates R02/R06).
   Announce it in one line.
3. Implement the smallest shippable slice. Reuse existing modules; UI stays in
   the Questflow design language.
4. Run the FULL gate (incl. the populated-demo smoke on a seeded local stack).
   Fix until green — persist (AutoLab), don't thrash.
5. Spawn a SEPARATE verifier subagent (fresh context) → verdict in Notes.
   For "deployed" claims the verifier must confirm you did NOT fake the live
   check; those stay BLOCKED-ON-DEPLOY with the exact command.
6. Update the ticket row + append one AutoLab line. Commit
   `feat(live-loop): <ID> <summary>`, push, refresh the PR per the remote
   workflow.

## AutoLab log

- 2026-07-06 bootstrap: baseline = loop-1 (O02–O08) merged-ready on PR #41,
  CI green; two demo root causes already FIXED this session (frontend real-URL
  default + CORS preview-origin allow). Loop authored: 8 tickets (R01 gates the
  rest; R02+R07 are the seed + benchmark that make the demo non-empty offline;
  R03–R06 fix the specific broken screens from the owner's screenshots).
  outcome = ready. Owner action still required for the live site: factory-reboot
  the HF Space so the deployed backend serves current code + data.
