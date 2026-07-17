# Loop V67 — Public-launch polish · STATE

Worktree: `E:/polymarket-worktrees/loop67-polish` · branch `loop67/launch-polish`  
Scope: **frontend only**. Binding: `GOAL.md`. Never push/merge.

## Ticket status

| Ticket | Status | Evidence |
|---|---|---|
| L1 `/terms` + `/about` + footer links | **DONE** | commit `feat(loop67): L1 …` |
| L2 Metadata / OG / favicon / robots / sitemap | **DONE** | commit `feat(loop67): L2 …` |
| L3 Branded 404/error + API-down banner | **DONE** | commit `feat(loop67): L3 …` |
| L4 Lighthouse sanity (max 3 cheap fixes) | **DONE** | scores + fixes below |
| L5 Gate (typecheck / lint / vitest / build) | **PENDING** | counts after L5 |

## L4 — Lighthouse (local prod build)

**Setup:** `npm run build` then `npm run start -- --port 3767`  
**Target:** `http://localhost:3767/`  
**Tool:** lighthouse@12.6.1 (headless Chrome)  
**Artifact:** `goals/loop-v67-launch-polish/lighthouse-home.json` (baseline pre-fix run)

### Baseline category scores (home)

| Category | Score |
|---|---|
| Performance | **41** |
| Accessibility | **88** |
| Best Practices | **96** |
| SEO | **100** |

### Cheap fixes applied (max 3)

1. **a11y label-content-name-mismatch** — logo link `aria-label` now includes visible `AE` + `AlphaEdge`; alerts bell accessible name includes visible badge (`9+` / count).
2. **a11y list / listitem** — HomeHero loops: `<li>` is a direct child of `<ol>` (MotionReveal moved inside `li`).
3. **a11y target-size** — QuestArenaHero slide dots enlarged to ≥24×24px hit targets.

### Parked (unresolved — what to check next)

| Issue | Score signal | Why parked | Next check |
|---|---|---|---|
| TBT / long tasks / bootup JS | perf 41; TBT 14s lab | Heavy home client tree (discover rails, framer, charts) — not a <1h polish | Profile with React Profiler; code-split QuestDiscoverShell / framer; defer non-LCP rails |
| LCP ~6.8s | LCP element on home | Same JS main-thread contention | Isolate LCP text block; reduce above-fold client JS |
| DOM size ~13.5k nodes | excessive DOM | Feed/markets rails mount large lists | Virtualize tickers/boards; cap initial SSR list size |
| Font sizes &lt;12px | ~40% text &lt;12px | Widespread mono labels / `text-[10px]`/`[11px]` design tokens | Token pass to min 12px on public marketing surfaces only |
| Unused / legacy JS | ~49 KiB / 11 KiB | Next/polyfill noise | Bundle analyzer; modern browserslist |
| bfcache blocked | 2 reasons | Client listeners / cache headers | Audit unload listeners and Cache-Control after perf pass |
| Source maps missing (prod) | best-practices nit | Intentional for public build size | Optional `productionBrowserSourceMaps` for internal only |

**Guardrail:** no fabricated Lighthouse scores; no new product libraries; paper-trading truth unchanged.
