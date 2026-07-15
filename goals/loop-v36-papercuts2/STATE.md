# loop-v36-papercuts2 — STATE

## LOOP LOG
| step | date | result | proof |
|------|------|--------|-------|
| Q1 | 2026-07-15 | DONE — unfixed V35 backlog closed | PC08 dark-only pin; PC09 honest empty CTAs; evidence under `evidence/` |
| Q2 | 2026-07-15 | DONE — local V35 sweep + PC10 | PC01–PC09 verify clean; NEW PC10 header overflow fixed |
| Q3 | 2026-07-15 | DONE — FE gates + full PW + review | typecheck/lint/vitest/build + PW 29 pass / 1 skip |

## Truth vs GOAL “13 papercuts”
V35 STATE filed **9** evidence-backed papercuts (PC01–PC09), not 13.
PC01–PC07 FIXED in V35; PC08/PC09 were deferred. V36 treats those two as the
remaining unfixed backlog and closes them without inventing light theme or
fake traders.

## Q1 unfixed → fixed

| ID | Was | V36 action | Evidence |
|----|-----|------------|----------|
| PC08 | deferred dark-only | Pin `color-scheme: dark` + viewport `themeColor`; no fake toggle | `evidence/PC08_dark_only_home.png` |
| PC09 | empty arena / no `/traders` | Honest empty + Browse markets / Open feed; trader 404 CTAs | `evidence/PC09_*.png` |

Commits: `12f23d2`, `d8ef10f`, `858a8ba`

## Q2 local re-sweep
- Script: `goals/loop-v35-papercuts/sweep.mjs` with `SWEEP_BASE=http://127.0.0.1:31017`
- Verify: `goals/loop-v36-papercuts2/verify-fixed.mjs` → **allOk: true** (`evidence/q2-pc-verify.json`)
- Raw: `evidence/q2-sweep/sweep-raw.json` (22 heuristic hits)

### Confirmed clean
PC01–PC09 all ok on local (search readable, Markets h1, no raw alert slugs,
eval no harness dump, portfolio `?next=`, title humanize, honest empties,
dark-only, no invented standings).

### NEW filed
| ID | Finding | Disposition |
|----|---------|-------------|
| PC10 | Header cluster overflow at 1280 (`scrollWidth` 1358; NotificationBell past viewport) | **FIXED** — defer Home/Clones to More below xl, tighten search/auth, `overflow-x-hidden`; `evidence/PC10_header_no_overflow.png` |
| PC-THEME-01 | No theme toggle | = PC08 by design (documented, not invented) |
| PC-OX-* | body.scrollWidth > clientWidth | Mostly ticker clipped content; after PC10 `scrollWidth==1280`, `pageCanScrollX=false` |
| PC-CONTRAST-* | `bg-*-dim` fills without `text-bg` | Heuristic false positives on dim/tinted surfaces; solid accent CTAs already use `text-bg` |
| Hydration warnings | SSR/client attr mismatch on several routes | Documented residual — not in Q1–Q3 FE papercut scope |

Commit: `3762a39`

## Q3 gate counts (pasted)
```
typecheck: exit 0
lint:      exit 0
vitest:    Test Files 66 passed (66) | Tests 382 passed (382)
build:     exit 0
playwright: 29 passed, 1 skipped (3.6m)  PW_EXIT=0
```

## Adversarial self-review (fresh)
- **Scope:** Only `frontend/src/**` + `goals/loop-v36-papercuts2/**` (+ minimal
  `SWEEP_BASE`/`SWEEP_EVIDENCE` env hooks in V35 `sweep.mjs`). No backend,
  no e2e-spec logic, no deploy, no push/merge.
- **Invented issues?** No — PC08/PC09 came from V35 evidence; PC10 from local
  sweep + DOM probe (`aside.relative` NotificationBell at right=1358).
- **text-bg on accent:** New CTAs use `bg-primary`/`bg-accent` + `text-bg`.
- **Honest empties:** Leaderboard/trader empties explain *why* and link out;
  no demo standings when live API returns [].
- **PC01 regression check:** Search ~172px, placeholder unclipped, page
  `scrollWidth=1280` — better than original crush+clip without reintroducing
  horizontal page scroll.
- **Residual risk:** Sign up deferred below xl in header (still on `/auth/signup`
  + mobile menu); Home/Clones live under More below xl; hydration console noise
  remains; contrast heuristic still noisy on `-dim` fills.
- **AutoLab:** not applicable (no iterative measure) — one-shot UX papercuts.

## Verdict
**Q1–Q3 DONE.**

AutoLab: not applicable (no iterative measure)

### ORCHESTRATOR REVIEW · Q1-Q3 · verdict: PASS — LOOP V36 COMPLETE
Backlog cleared with evidence; gates green. Lane closed.
