# loop-v35-papercuts — STATE

## LOOP LOG
| step | date | result | proof |
|------|------|--------|-------|
| U1 | 2026-07-15 | DONE — evidence-backed papercut list | prod sweep chromium 1280+375 dark+html.light; screenshots under `evidence/` |
| U2 | 2026-07-15 | DONE — PC01–PC07 fixed (7 commits + JSX follow-up) | see commits `e594eda`…`b68e0e9` |
| U3 | 2026-07-15 | DONE — gates + playwright green | typecheck/lint/vitest/build + PW 29 pass / 1 skip; `gate.py` PASS |

## U1 Sweep notes
- Prod: https://alphaedge-frontend-three.vercel.app (READ-ONLY)
- Routes: `/` `/markets` market detail `/portfolio` `/leaderboard` `/signals` `/eval` `/alerts` `/feed`
- `/traders/<any>`: **unavailable** — leaderboard honest-empty (“No ranked traders yet”); feed has no `/traders/` links while logged out. Not invented.
- Theme toggle: **none in chrome**. `html.light` flips chart tokens only; body stays `rgb(7,11,10)` (dark-only redesign). Sweep still captured light residual shots.

## Papercut list (evidence-only; ranked by user impact)

| ID | Impact | Finding | Evidence | U2 |
|----|--------|---------|----------|----|
| PC01 | HIGH | Header search squeezed (~165px). Placeholder clipped | `evidence/PC01_search_crushed_header.png` | FIXED — min-w + shorter placeholder |
| PC02 | HIGH | `/alerts` raw `pm-…` slugs | `evidence/PC02_*.png` | FIXED — `formatMarketLabel` |
| PC03 | MED-HIGH | `/markets` no `<h1>` | `evidence/PC03_markets_no_h1.png` | FIXED — Markets h1 |
| PC04 | MED | `/eval` harness dump | `evidence/PC04_eval_autolab_dump.png` | FIXED — honest user copy |
| PC05 | MED | `/portfolio` → login, no `next=` | `evidence/PC05_*.png` | FIXED — `?next=/portfolio` + safeNextPath |
| PC06 | MED | Market `<title>` used raw slug | `evidence/PC06_*.png` | FIXED — `formatMarketLabel` fallback |
| PC07 | LOW-MED | Thin markets empty copy | `evidence/PC03_*.png` | FIXED — honest empty |
| PC08 | INFO | No theme toggle / light residual only | `evidence/PC08_*.png` | deferred (dark-only by design) |
| PC09 | INFO | Leaderboard empty — no `/traders` | `evidence/PC07_*.png` | data, not FE invent |

## U2 commits
1. `fix(loop35): U2 header search width and placeholder`
2. `fix(loop35): U2 alerts humanize market titles`
3. `fix(loop35): U2 markets h1 and honest empty copy`
4. `fix(loop35): U2 eval empty without harness dump`
5. `fix(loop35): U2 portfolio login next return path`
6. `fix(loop35): U2 market metadata title humanize fallback`
7. `fix(loop35): U2 markets empty-state JSX parent` (typecheck catch)

## U3 gate counts (pasted)
```
typecheck: exit 0
lint:      exit 0
vitest:    Test Files 66 passed (66) | Tests 382 passed (382)
build:     exit 0
playwright: 29 passed, 1 skipped (6.4m)  PW_EXIT=0
gate.py:   PASS: all checks green (backend 1609 passed, 28 skipped; ruff; FE typecheck/lint/vitest/build)
```

## Adversarial self-review (fresh)
- **Scope:** Only `frontend/src/**` + `goals/loop-v35-papercuts/**`. No backend, no e2e-spec logic, no deploy, no push/merge.
- **Invented issues?** No — each PC has a screenshot; PC08/PC09 documented not “fixed” with fake UI/data.
- **text-bg on accent:** Touched CTAs already used `text-bg` / `text-bg` on accent fills; no new accent fills without it.
- **Honest empties:** Eval/markets empties explain *why*; leaderboard empty left alone (already honest).
- **Security:** `safeNextPath` rejects `//` and absolute URLs on login `next=`.
- **Residual risk:** Prod still dark-only (PC08); `/traders` needs ranked paper traders (PC09). Market `<title>` still needs live API for full question text — humanize is fallback only.
- **AutoLab:** not applicable (no iterative measure) — one-shot UX papercuts.

## Verdict
**U1–U3 DONE.**
