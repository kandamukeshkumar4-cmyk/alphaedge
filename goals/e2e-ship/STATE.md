# E2E Ship — make the deployed homepage live-data-first (2026-07-08)

Single goal: kill the mock-data homepage so the 185 real Polymarket markets
(and Kalshi) render on prod. Verifier = `py -3.13 scripts/verify_prod.py`
must exit 0 (all 6 checks PASS). Today check 5 FAILS by design.

## PROD FACTS (verified 2026-07-07, ground truth)

- Backend prod: https://mukeshkumar007-alphaedge-api.hf.space — HEALTHY,
  serves 287 markets (185 open polymarket, 12 open kalshi, 16 seed), live
  candles, signals, LLM briefs.
- Frontend prod: https://alphaedge-frontend-three.vercel.app (Vercel project
  "alphaedge-frontend"). The Azure SWA URL is DEAD (404) and
  frontend-kappa-drab-22.vercel.app belongs to a DIFFERENT project — never
  touch either.
- Backend deploys automatically on push to branch codex/alphaedge-base via
  .github/workflows/deploy-hf-space.yml.
- THE CORE DEFECT: the deployed homepage renders only seed/demo markets and a
  fake "Live trades" ticker from frontend/src/lib/mock-data.ts, hiding the 185
  real Polymarket markets.

## LOOP LOG

| loop | date | result | proof |
|------|------|--------|-------|
| 0 | 2026-07-08 | setup done; checks 1-4,6 PASS, check 5 FAILS (by design) | verify_prod.py: 5/6 — health ok; markets total=322 open+locked=300 polymarket=282 kalshi=18; live candles pm-will-morocco-...; signals=5; FE alpha_quant present + 0/282 pm- slugs; memories 200. NOTE prod-facts counts (287/185/12) now stale (322/282/18), non-blocking |
| 1 | 2026-07-08 | backlog shipped: merged 3 loop3-agent-memory commits into base, pushed, backend+frontend deployed to prod; checks 1-4,6 PASS, 5 FAILS by design | verify_prod.py: 5/6 — 1 health PASS (200 ok); 2 markets PASS (total=324 open+locked=302 polymarket=284 kalshi=18); 3 candles PASS (live pm-will-morocco-win-the-2026-fifa-world-cup-464); 4 signals PASS (count=5); 5 frontend-live FAIL (alpha_quant present, 0/284 pm- slugs — by design, loops 2-5 fix this); 6 memories PASS (200). Merge: 7a06c6a (loop0 e2e state+verifier, loop1 hermetic ensemble test, loop2 dead component removal+plan007). Push: 5c85732..c2ac741. HF deploy run 28956631913 success 3m39s. Vercel prod READY aliased alphaedge-frontend-three.vercel.app. |

## BLOCKED

(none)

## NEXT

- Loop 1: Trace homepage data flow — confirm mock-data.ts drives the seed rails + fake Live trades ticker
- Loop 2: Replace homepage market rails with the live /api/v1/markets catalog (pm- slugs)
- Loop 3: Remove the fake "Live trades" ticker (alpha_quant) / wire to real market activity
- Loop 4: Bake the live catalog into the static export so pm- slugs render in HTML/JS (SSG)
- Loop 5: Build + deploy frontend to Vercel prod; run verify_prod.py — drive check 5 to PASS
- Loop 6: Full verify_prod.py green (all 6 checks PASS); commit + handoff
