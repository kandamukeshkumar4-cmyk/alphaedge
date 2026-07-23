# STATE88C — Graph V88, node K-C (frontend, loop88-ui worktree)

Scope charter: `frontend/src/app/scanners/**`,
`frontend/src/components/scanners/**`, `frontend/src/lib/scanners-api.ts`,
`frontend/e2e/scanners.spec.ts`, `STATE88C.md` ONLY. Paper-trading simulation
only — scanners are research artifacts; no order path is touched.

Backend LIVE (node P-B, loop87/88): run rows carry `repairs`
(`[{node, class, action}]`) + `repairs_count` (mirrored from
`result.repairs`); compile returns `{spec, compiler:
"deterministic"|"llm-assisted", warnings: [...]}`.

## Tickets

- **V1 — repairs visibility**: `/scanners/[id]` run panel shows an amber
  "Self-healed xN" chip when repairs exist; expanding lists each repair as
  `<node>: <class> -> <action>` in mono. Runs-history rows show a count chip.
  No red styling.
- **V2 — compile feedback**: composer preview shows a "Compiled:
  deterministic|AI-assisted" badge (mint / blue) and renders `warnings[]` as
  amber notice lines above the Create button.
- **V3 — e2e**: DOM assertions for V1+V2 from mock data (mock client gained
  `repairs` + `warnings` fields).

## Proof log

Baseline (before V1 edits, after `npm ci`):

```
$ cd frontend && npm run typecheck && npm run lint
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

### V1 — repairs visibility

```
$ cd frontend && npm run typecheck
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

$ npm run lint
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

(both exit 0, no output = clean)

```
$ git log -1   # (recorded post-commit; folded in here)
commit 5034c03cb9e577125fd7fc00a21bc61428ea2c84
Author: kandamukeshkumar4-cmyk <271247509+kandamukeshkumar4-cmyk@users.noreply.github.com>
Date:   Thu Jul 23 11:12:27 2026 -0400

    feat(loop88): V1 — repairs visibility

    Run panel on /scanners/[id] shows an amber 'Self-healed xN' chip when the
    run carries executor repairs (backend loop87: 8-class classifier, bounded
    repairs); expanding lists each repair as '<node>: <class> -> <action>' in
    mono. Runs-history rows show a compact amber count chip. Never red.

    - scanners-api: ScannerRepair type, repairs on ScannerRun (top-level with
      result.repairs fallback), tolerant normalizer, runRepairsCount helper,
      mock store seeds deterministic repairs on the whale scanner's runs.
    - ScannerDetailShell: SelfHealChip (aria-expanded) + RepairLedger
      (grid-rows expand, motion-reduce safe) + RunRepairsChip on history rows.

    Verified: npm run typecheck && npm run lint (both exit 0).

    Co-Authored-By: Claude <noreply@anthropic.com>
```

### V2 — compile feedback

```
$ cd frontend && npm run typecheck
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

$ npm run lint
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

$ npx vitest run src/lib/scanners-api.test.ts
 Test Files  1 passed (1)
      Tests  4 passed (4)
   Duration  1.40s
```

(typecheck + lint exit 0, no output = clean; existing scanners-api unit
suite still green after the additive `compiler` / `warnings` fields)

```
$ git log -1   # (recorded post-commit; folded in here)
commit df00efa9c0d093c1b6cc24fbc2dc6a8e0b9f654f
Author: kandamukeshkumar4-cmyk <271247509+kandamukeshkumar4-cmyk@users.noreply.github.com>
Date:   Thu Jul 23 11:15:22 2026 -0400

    feat(loop88): V2 — compile feedback

    Composer preview shows which compiler path produced the spec — a small
    'Compiled: deterministic' badge (mint) or 'Compiled: AI-assisted' (blue) —
    and renders the backend's deterministic warnings[] as amber notice lines
    above the Create button (never blocking, never red).

    - scanners-api: compileScanner now returns {spec, compiler, warnings,
      source}; live branch parses compiler/warnings defensively, mock branch
      reports 'deterministic' with specWarningsLocal mirroring the backend's
      validate_spec (same rules, same strings).
    - ScannerComposer: CompilerBadge in the preview header, warnings list
      above the Create row.

    Verified: npm run typecheck && npm run lint (exit 0) + vitest
    scanners-api.test.ts 4/4 passed.

    Co-Authored-By: Claude <noreply@anthropic.com>
```

### V3 — e2e coverage for V1+V2

Mock client seeds `repairs` (whale scanner's two runs: x2 and x1) and the
compile mock returns `compiler: "deterministic"` + `specWarningsLocal`
warnings, so the DOM assertions run without the backend. One e2e fix
iteration: `scanner-repair-ledger` testid moved from the inner `<ul>` to the
collapsible grid wrapper (where `aria-hidden` lives).

```
$ cd frontend && npm run typecheck
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

$ npm run lint
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

$ npm run build
> alphaedge-frontend@0.1.0 build
> next build
   Creating an optimized production build ...
 ✓ Compiled successfully in 12.6s
   Linting and checking validity of types ...
 ✓ Generating static pages (113/113)
├ ○ /scanners                                    5.82 kB         129 kB
├ ƒ /scanners/[id]                               92.1 kB         216 kB

$ npx next start -p 31099 &        # served the build
 ✓ Ready in 1219ms

$ E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/scanners.spec.ts --project=chromium
Running 7 tests using 1 worker

  ok 1 [chromium] › e2e\scanners.spec.ts:20:7 › V84 Scanner Studio › /scanners renders the list from mock and a compile preview appears (1.5s)
  ok 2 [chromium] › e2e\scanners.spec.ts:50:7 › V84 Scanner Studio › scanner detail renders the pipeline canvas with >=3 nodes (1.9s)
  ok 3 [chromium] › e2e\scanners.spec.ts:79:7 › V84 Scanner Studio › draft scanner shows the Test & publish panel and version chip (1.3s)
  ok 4 [chromium] › e2e\scanners.spec.ts:123:7 › V84 Scanner Studio › active scanner shows the version chip with rollback history (1.4s)
  ok 5 [chromium] › e2e\scanners.spec.ts:149:7 › V84 Scanner Studio › Run now shows the build narration rail (X3) (1.3s)
  ok 6 [chromium] › e2e\scanners.spec.ts:167:7 › V84 Scanner Studio › V1 — self-heal repairs chip + ledger on the latest run, count chips on history rows (1.9s)
  ok 7 [chromium] › e2e\scanners.spec.ts:217:7 › V84 Scanner Studio › V2 — compile badge + warnings in the describe-a-scanner preview (1.1s)

  7 passed (11.6s)
```

`git log -1` for the V3 commit:

```
$ git log -1   # (recorded post-commit; folded in here)
commit 9eabc43e13e4d02096a0d268667c531c84bbddb3
Author: kandamukeshkumar4-cmyk <271247509+kandamukeshkumar4-cmyk@users.noreply.github.com>
Date:   Thu Jul 23 11:25:02 2026 -0400

    feat(loop88): V3 — e2e coverage for repairs + compile feedback

    Extends e2e/scanners.spec.ts with DOM assertions driven by the mock
    client's seeded data (no backend needed):

    - V1: amber 'Self-healed x2' chip on the latest-run panel with
      aria-expanded toggle; expanded ledger lists each repair as
      '<node>: <class> -> <action>' in mono; runs-history rows carry x2/x1
      count chips (newest first).
    - V2: 'Compiled: deterministic' mint badge in the preview, warnings[]
      rendered as amber notice lines above Create (spend-warning compile),
      and a geometry check that warnings sit above the Create button.

    The scanner-repair-ledger testid moved from the inner <ul> to the
    collapsible grid wrapper so the aria-hidden contract is directly
    assertable.

    Verified: npm run typecheck && npm run lint (exit 0); npm run build
    (Compiled successfully, 113/113 static pages); playwright suite
    e2e/scanners.spec.ts --project=chromium 7 passed (11.6s) against
    next start on :31099.

    Co-Authored-By: Claude <noreply@anthropic.com>
```

AutoLab: not applicable (no iterative measure — one-shot V1–V3 feature
tickets; verified by typecheck/lint/build/e2e gates above).

Guardrails honored: `PAPER_TRADING_ONLY` untouched; no order path changes;
reduced-motion respected (grid-rows transition gated by
`motion-reduce:transition-none`, chevron rotation likewise); reserved
heights preserved (skeleton/narration rails untouched; ledger expansion is
a standard accordion below the header); no red styling anywhere (amber/gold
for heal chips + warnings, mint/blue for the compiler badge). Rule budget:
2 retries max per command; no strikes exhausted, no escalation needed.

STATUS: **DONE** (V1–V3 committed — 5034c03, df00efa, 9eabc43, + this proof
commit; no push, no deploy).

