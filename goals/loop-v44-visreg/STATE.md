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

## CI policy (S3)

- `snapshotPathTemplate` includes `{platform}` so win32 ≠ linux baselines.
- `chromium` project `testIgnore`s `visreg.spec.ts` — CI
  `npx playwright test --project=chromium` unchanged.
- `visreg` project is **local-only**. Ubuntu baseline generation via ci-e2e
  is **not** wired (non-trivial artifact commit loop); do not break green CI.
- Local: `npx playwright test --project=visreg` (update with
  `--update-snapshots`).

## LOOP LOG

| loop | date | result | proof |
|------|------|--------|-------|
| S1 | 2026-07-15 | IN_PROGRESS | stable-shot.ts + masking rules |
