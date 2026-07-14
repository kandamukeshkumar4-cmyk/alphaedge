# Loop V17 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| Q1 | Playwright scaffold + smoke | DONE | Local stack: isolated SQLite + real uvicorn + next dev. Smoke green. |
| Q2 | Discover freshness journey | TODO | |
| Q3 | Trade journey | TODO | |
| Q4 | Coverage journeys + one-command run | TODO | |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| frontend/package.json | Q1 | DONE — additive `test:e2e` script line only |

## BUG REPORTS (app bugs found by journeys — do not fix here)

## GATE TAILS (Q1)
```
> typecheck → tsc --noEmit  (exit 0)
> lint → eslint src --max-warnings=0  (exit 0)
> test → Test Files 55 passed (55); Tests 341 passed (341)
> npx playwright test:
  1 skipped (legacy mock-stub retired)
  1 passed — Q1 smoke / markets grid non-empty + zero console errors
  (1.7m, chromium)
```

## VERIFIER VERDICT (Q1) — adversarial self-review
- PASS scope: only frontend/e2e/**, playwright.config.ts, package.json test:e2e line, STATE.md. No frontend/src/**, no backend/**.
- PASS stack: start-local-stack.mjs boots real uvicorn with PAPER_TRADING_ONLY=true, LIVE_FEED + schedulers off, isolated SQLite create_all via e2e helper (A6/E5 pattern). next dev with NEXT_PUBLIC_API_URL → local API only (no Railway).
- PASS smoke: `/` renders market links (`a[href^="/markets/"]` count > 0), console noise filter excludes net::ERR/WS only.
- PASS guardrails: paper-only env forced; no prod URL; no order-path changes.
- Residual risk: Windows shell spawn required for uv/npm; stack boot ~1–2 min cold.

## LOOP LOG
- 2026-07-13 · Q1 start · branch loop17/e2e-qa clean at 30ecbee · claiming frontend/package.json for test:e2e
- 2026-07-13 · Q1 DONE · scaffold + smoke green · gate pasted above · verifier PASS
