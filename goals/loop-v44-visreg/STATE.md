# loop-v44-visreg — STATE

## Masking rules (S1)

Playwright-side only — **zero `frontend/src` edits**.

| Region | Technique | Selector / method |
|--------|-----------|-------------------|
| Prices / pts / $ | `mask` | `main .font-mono` matching ¢\|pts\|$\|% ; `main p.font-mono` |
| Sparklines | `mask` | `main div.h-9`, `main svg[viewBox]` |
| Charts | `mask` | `[role=img]` price history, `main canvas` |
| Live ticker | `mask` | `div.sticky.bottom-0` |
| Relative ages | freeze text | walk text nodes → `\d+[smhd] ago` → `• ago` |
| Motion | freeze CSS | `reducedMotion` + `animation/transition: none` |
| Health banner | `mask` | `[data-testid=health-banner]` |
| Portfolio banner | `mask` | sticky top strip with Bankroll/Unreal |
| Header auth | `mask` | `header [title*='@']`, header `$…` chip |

Shot mode: **viewport-only** (`fullPage: false`) — full-page heights drift when
lazy sections settle differently (and after chromium mutates shared SQLite).

## CI policy (S3)

- `snapshotPathTemplate` includes `{platform}` → win32 ≠ linux filenames.
- Committed baselines: `*-visreg-win32.png` only (24 files).
- `chromium` project `testIgnore`s `visreg.spec.ts` — CI
  `npx playwright test --project=chromium` unchanged / cannot miss ubuntu PNGs.
- `visreg` project runs **first** locally (before chromium) so the shared e2e
  SQLite is still pristine for shots.
- **ci-e2e NOT extended** — generating ubuntu baselines needs an artifact
  commit loop (non-trivial); scoping to local keeps green CI intact.
- Local update: `npx playwright test --project=visreg --update-snapshots`

## Gate counts (pasted)

```
lint:       exit 0  (eslint src --max-warnings=0)
typecheck:  exit 0  (tsc --noEmit)
vitest:     Test Files 67 passed (67) | Tests 385 passed (385)
build:      exit 0
visreg×2:   24 passed (2.1m) ; 24 passed (2.0m)
playwright: 53 passed, 1 skipped (4.9m)  PW_EXIT=0
gate.py --frontend-only:
  PASS frontend typecheck / test / build
  === GATE VERDICT ===
  PASS: all checks green
```

## Adversarial self-review (fresh)

- **Scope:** `frontend/e2e/**`, `frontend/playwright.config.ts`,
  `goals/loop-v44-visreg/**` only. `git diff` shows **zero** `frontend/src`
  edits. No push/merge.
- **CI unbroken?** Yes — `--project=chromium` ignores visreg; no workflow
  edit. Missing linux PNGs cannot fail CI.
- **Stability?** Two consecutive visreg-only greens after viewport switch;
  full suite green with visreg-first project order. Earlier flake was
  fullPage height (2261→2853) after chromium mutated SQLite — fixed.
- **Masking honest?** Masks prices/sparklines/tickers/ages/live chrome; does
  not hide layout chrome under test (header/nav/structure still compared).
- **Theme coverage:** dark (default) + `html.light` (chart/token flip; app is
  dark-only in product UI per PC08 — light is forced for the matrix).
- **Residual risk:** win32-only baselines; ubuntu CI will not catch visual
  regressions until linux PNGs are generated in a future dedicated job.
  Atlas panel / toast races could still flake under load — maxDiffPixelRatio
  0.02 is a soft AA cushion, not a free pass on layout.
- **Never violated:** no frontend/src, no CI break, no push/merge.

## LOOP LOG

| loop | date | result | proof |
|------|------|--------|-------|
| S1 | 2026-07-15 | DONE | `aaf26d9` stable-shot.ts + masking table |
| S2 | 2026-07-15 | DONE | `60ecbc2` 24 win32 PNGs; 2×24 green after viewport fix |
| S3 | 2026-07-15 | DONE | platform template; visreg local-only; FE gates + PW 53/1 |

## Verdict

**S1–S3 DONE.**

AutoLab: not applicable (no iterative measure)

### ORCHESTRATOR REVIEW · S1-S3 · verdict: PASS — LOOP V44 COMPLETE
24 platform-tagged baselines, 2x consecutive green, viewport-only fix for the
flaky full-page shot, CI provably untouched. Lane closed.
