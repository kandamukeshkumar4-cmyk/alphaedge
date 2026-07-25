# STATE111-ESLINT — eslint@10 migration attempt to clear GHSA-mh99 (brace-expansion OOM DoS)

Worktree: `E:/polymarket-worktrees/loop111-eslint10` (branch `loop111-eslint10/node`, base `9d447a3`).

**OUTCOME: BLOCKED-UPSTREAM.** The advisory cannot be cleared today. Two
independent upstream blockers, both proven empirically below. Per charter the
tree was reverted (`git checkout -- frontend/package.json
frontend/package-lock.json`); the only file this loop adds is this document.

Charter respected: no backend, no alembic, no `--force` npm operations, no push,
no deploy, PAPER_TRADING_ONLY untouched, no secrets printed, no `git add -A`.

---

## Context

`STATE107-NPMSEC.md` (worktree `E:/polymarket-worktrees/loop107-npmsec`) closed
4 of 5 high-severity frontend advisories and left exactly one ACCEPTED-RISK item:

- **GHSA-mh99-v99m-4gvg** — `brace-expansion`: DoS via unbounded expansion length
  causing an out-of-memory process crash. Reported by npm as 9 findings via the
  `depends-on` cascade.

Loop 107 also empirically proved that a blanket `overrides: { "brace-expansion":
"^5.0.8" }` **breaks eslint** — brace-expansion 5.x exports `{ expand }` (named)
while `minimatch@3` does `expand = require('brace-expansion'); expand(pattern)`,
producing `TypeError: expand is not a function`. That path was **not retried**
in this loop.

Loop 107's stated upgrade path — "bump eslint to 10.x together with a compatible
eslint-config-next" — is the hypothesis this loop tested. **It does not hold.**

---

## STEP 1 — Version reconnaissance (verbatim `npm view`)

### Current versions (frontend/package.json, base 9d447a3)

```
"eslint": "^9.39.4"
"eslint-config-next": "^16.2.6"
"next": "^15.1.0"          (resolves to next@15.5.21)
"typescript": "^5.7.0"
```

Local toolchain: `node -v` → `v24.14.0`, `npm -v` → `11.9.0`.

### eslint dist-tags

```
$ npm view eslint dist-tags --json
{
  "es6jsx": "0.11.0-alpha.0",
  "next": "10.0.0-rc.2",
  "maintenance": "9.39.5",
  "latest": "10.8.0"
}
```

`eslint@10.8.0` is the version npm's own audit remediation points at
("Will install eslint@10.8.0, which is a breaking change").

### eslint@10.8.0 engines / peers — both satisfied

```
$ npm view eslint@10.8.0 engines peerDependencies --json
{
  "engines": { "node": "^20.19.0 || ^22.13.0 || >=24" },
  "peerDependencies": { "jiti": "*" }
}

$ npm view eslint@10.8.0 peerDependenciesMeta --json
{ "jiti": { "optional": true } }
```

Node 24.14.0 satisfies `>=24`; the `jiti` peer is optional. No blocker here.

### eslint@10.8.0 already uses the patched brace-expansion line

```
$ npm view eslint@10.8.0 dependencies --json     (excerpt)
  "minimatch": "^10.2.5",
  "@eslint/config-array": "^0.23.5",
  ...                                (note: no "@eslint/eslintrc")

$ npm view @eslint/config-array@0.23.5 dependencies --json
{ "@eslint/object-schema": "^3.0.5", "debug": "^4.3.1", "minimatch": "^10.2.4" }
```

So eslint core itself is clean on eslint@10: `minimatch@10` →
`brace-expansion@5.0.8` (patched), and `@eslint/eslintrc` (the js-yaml carrier)
is gone entirely.

### eslint-config-next — a compatible release DOES exist (peer-wise)

```
$ npm view eslint-config-next dist-tags --json    (excerpt)
{ "latest": "16.2.11", "preview": "16.3.0-preview.9", "canary": "16.3.0-canary.96", ... }

$ npm view eslint-config-next@16.2.11 peerDependencies dependencies --json
{
  "peerDependencies": { "eslint": ">=9.0.0", "typescript": ">=3.3.1" },
  "dependencies": {
    "globals": "16.4.0",
    "typescript-eslint": "^8.46.0",
    "eslint-plugin-react": "^7.37.0",
    "eslint-plugin-import": "^2.32.0",
    "eslint-plugin-jsx-a11y": "^6.10.0",
    "@next/eslint-plugin-next": "16.2.11",
    "eslint-plugin-react-hooks": "^7.0.0",
    "eslint-import-resolver-node": "^0.3.6",
    "eslint-import-resolver-typescript": "^3.5.2"
  }
}
```

`eslint-config-next`'s declared peer `eslint: ">=9.0.0"` **admits eslint@10**, so
on the surface this looked viable. That peer range is misleadingly permissive —
see STEP 3. The identical dependency set holds on `16.3.0-preview.9` and
`16.3.0-canary.96`, i.e. there is no future line that changes the outcome.

`next@15.5.21` does not constrain eslint at all (eslint/eslint-config-next are
devDependencies of this repo, not peers of `next`).

---

## STEP 2 — BLOCKER A: the advisory survives eslint@10 (measured, not predicted)

### Baseline (after `npm ci` at base 9d447a3)

```
# npm audit report

brace-expansion  <=5.0.7
Severity: high
brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash - https://github.com/advisories/GHSA-mh99-v99m-4gvg
fix available via `npm audit fix --force`
Will install eslint@10.8.0, which is a breaking change
node_modules/minimatch/node_modules/brace-expansion
  minimatch  2.0.0 - 10.0.2
  Depends on vulnerable versions of brace-expansion
  node_modules/minimatch
    @eslint/config-array  <=0.22.0
    Depends on vulnerable versions of minimatch
    node_modules/@eslint/config-array
      eslint  0.12.0 - 2.0.0-rc.1 || 4.1.0 - 10.0.0-rc.2
      Depends on vulnerable versions of @eslint/config-array
      Depends on vulnerable versions of @eslint/eslintrc
      Depends on vulnerable versions of minimatch
      node_modules/eslint
    @eslint/eslintrc  0.0.1 || >=0.1.1
    Depends on vulnerable versions of minimatch
    node_modules/@eslint/eslintrc
    eslint-plugin-import  >=1.15.0
    Depends on vulnerable versions of minimatch
    node_modules/eslint-plugin-import
      eslint-config-next  >=10.2.1-canary.2
      Depends on vulnerable versions of eslint-plugin-import
      Depends on vulnerable versions of eslint-plugin-jsx-a11y
      Depends on vulnerable versions of eslint-plugin-react
      node_modules/eslint-config-next
    eslint-plugin-jsx-a11y  >=6.5.0
    Depends on vulnerable versions of minimatch
    node_modules/eslint-plugin-jsx-a11y
    eslint-plugin-react  >=7.23.0
    Depends on vulnerable versions of minimatch
    node_modules/eslint-plugin-react

9 high severity vulnerabilities
audit EXIT=1
```

### After the migration install (no `--force`)

```
$ npm install --save-dev eslint@^10.8.0 eslint-config-next@^16.2.11
npm warn ERESOLVE overriding peer dependency
npm warn ERESOLVE overriding peer dependency
npm warn ERESOLVE overriding peer dependency

added 11 packages, removed 29 packages, changed 58 packages, and audited 632 packages in 13s
6 high severity vulnerabilities
EXIT=0
```

```
$ npm audit --audit-level=high

# npm audit report

brace-expansion  <=5.0.7
Severity: high
brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash - https://github.com/advisories/GHSA-mh99-v99m-4gvg
fix available via `npm audit fix --force`
Will install eslint-config-next@12.0.4, which is a breaking change
node_modules/eslint-config-next/node_modules/brace-expansion
  minimatch  2.0.0 - 10.0.2
  Depends on vulnerable versions of brace-expansion
  node_modules/eslint-config-next/node_modules/minimatch
    eslint-plugin-import  >=1.15.0
    Depends on vulnerable versions of minimatch
    node_modules/eslint-config-next/node_modules/eslint-plugin-import
      eslint-config-next  >=10.2.1-canary.2
      Depends on vulnerable versions of eslint-plugin-import
      Depends on vulnerable versions of eslint-plugin-jsx-a11y
      Depends on vulnerable versions of eslint-plugin-react
      node_modules/eslint-config-next
    eslint-plugin-jsx-a11y  >=6.5.0
    Depends on vulnerable versions of minimatch
    node_modules/eslint-config-next/node_modules/eslint-plugin-jsx-a11y
    eslint-plugin-react  >=7.23.0
    Depends on vulnerable versions of minimatch
    node_modules/eslint-config-next/node_modules/eslint-plugin-react

6 high severity vulnerabilities
audit EXIT=1
```

**9 → 6, not 9 → 0.** eslint@10 removed `eslint`, `@eslint/eslintrc` and
`@eslint/config-array` from the cascade and moved top-level `minimatch` to
`10.2.5` / `brace-expansion@5.0.8`. The residual `minimatch@3.1.5` +
`brace-expansion@1.1.16` simply relocated to
`node_modules/eslint-config-next/node_modules/`, pulled in by three eslint
plugins that eslint-config-next depends on directly.

npm's newly-offered remediation is now `eslint-config-next@12.0.4` — a
Next-12-era downgrade. Rejected; not attempted.

### Why no version of this can be fixed today

All three residual carriers are already at their newest published release and
all three still pin `minimatch@^3.1.2`:

```
$ npm view eslint-plugin-import version;    → 2.32.0
$ npm view eslint-plugin-import dependencies.minimatch    → ^3.1.2
$ npm view eslint-plugin-jsx-a11y version;  → 6.10.2
$ npm view eslint-plugin-jsx-a11y dependencies.minimatch  → ^3.1.2
$ npm view eslint-plugin-react version;     → 7.37.5
$ npm view eslint-plugin-react dependencies.minimatch     → ^3.1.2
```

And `minimatch@3` can only ever resolve to a vulnerable brace-expansion:

```
$ npm view minimatch@3.1.5 dependencies --json
{ "brace-expansion": "^1.1.7" }

$ npm view brace-expansion versions   (tail)
... "1.1.14" "1.1.15" "1.1.16" | "2.0.0"..."2.1.2" | "3.0.0"..."3.0.2" | "4.0.0" "4.0.1" | "5.0.2"..."5.0.8"
```

`1.1.16` is the terminal 1.x release. The authoritative advisory range from the
npm registry confirms every pre-5.0.8 release is affected:

```
$ curl -s -X POST https://registry.npmjs.org/-/npm/v1/security/advisories/bulk \
    -H "Content-Type: application/json" \
    -d '{"brace-expansion":["1.1.16","2.0.3","4.0.1","5.0.8"]}'
...
{"id":1124334,"url":"https://github.com/advisories/GHSA-mh99-v99m-4gvg",
 "title":"brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash",
 "severity":"high","vulnerable_versions":"<=5.0.7","cwe":["CWE-400","CWE-770"],
 "cvss":{"score":7.5,"vectorString":"CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}}
```

`vulnerable_versions: "<=5.0.7"` covers the whole 1.x, 2.x, 3.x and 4.x lines.
The **only** safe release is `>=5.0.8`, whose named-export API `minimatch@3`
cannot consume (loop 107's proven crash). Therefore:

> Clearing GHSA-mh99 requires removing every `minimatch@3` from the tree.
> `eslint-plugin-import`, `eslint-plugin-jsx-a11y` and `eslint-plugin-react`
> have no published release that does so, and `eslint-config-next` has no
> published release (latest, preview, or canary) that avoids those plugins.

---

## STEP 3 — BLOCKER B: eslint@10 breaks the Next lint config outright

Beyond the security no-op, the migration is not even functional. With
eslint@10.8.0 + eslint-config-next@16.2.11 installed:

```
$ npx eslint --version
v10.8.0

$ npm run lint

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0


Oops! Something went wrong! :(

ESLint: 10.8.0

TypeError: Error while loading rule 'react/display-name': contextOrFilename.getFilename is not a function
Occurred while linting E:\polymarket-worktrees\loop111-eslint10\frontend\src\app\about\page.test.tsx
    at resolveBasedir (E:\polymarket-worktrees\loop111-eslint10\frontend\node_modules\eslint-config-next\node_modules\eslint-plugin-react\lib\util\version.js:31:100)
    at detectReactVersion (...\eslint-plugin-react\lib\util\version.js:85:19)
    at getReactVersionFromContext (...\eslint-plugin-react\lib\util\version.js:116:25)
    at testReactVersion (...\eslint-plugin-react\lib\util\version.js:181:28)
    at usedPropTypesInstructions (...\eslint-plugin-react\lib\util\usedPropTypes.js:307:36)
    at Components.componentRule (...\eslint-plugin-react\lib\util\Components.js:940:37)
    at createRuleListeners (...\node_modules\eslint\lib\linter\linter.js:497:15)
    at ...\node_modules\eslint\lib\linter\linter.js:623:7
    at Array.forEach (<anonymous>)
    at runRules (...\node_modules\eslint\lib\linter\linter.js:557:31)
lint EXIT=2
```

`context.getFilename()` was removed in eslint 10. `eslint-plugin-react@7.37.5`
still calls it. This is the concrete cause of the three
`npm warn ERESOLVE overriding peer dependency` warnings emitted during install —
none of the plugins eslint-config-next ships accept eslint 10:

```
$ npm view eslint-plugin-react@7.37.5 peerDependencies --json
{ "eslint": "^3 || ^4 || ^5 || ^6 || ^7 || ^8 || ^9.7" }

$ npm view eslint-plugin-jsx-a11y@6.10.2 peerDependencies --json
{ "eslint": "^3 || ^4 || ^5 || ^6 || ^7 || ^8 || ^9" }

$ npm view eslint-plugin-import@2.32.0 peerDependencies --json
{ "eslint": "^2 || ^3 || ^4 || ^5 || ^6 || ^7.2.0 || ^8 || ^9" }
```

Every one caps at eslint 9. `eslint-plugin-react` has no published version above
`7.37.5` (its `next` dist-tag is the ancient `7.8.0-rc.0`), so there is nothing
to bump or override to.

The only ways to make lint pass under eslint@10 would be to drop the
`eslint-config-next/core-web-vitals` preset or disable the React rule set —
both are **rule-set loosening**, explicitly forbidden by the charter. Not done.

**No inline `eslint-disable` comments were added anywhere in this loop.** No
source file was touched.

---

## STEP 4 — Flat config status (no migration needed)

The repo is already on eslint flat config; eslint 10's removal of `.eslintrc`
support is a no-op here. `frontend/eslint.config.mjs` is unchanged:

```js
import nextVitals from "eslint-config-next/core-web-vitals";

const config = [
  ...nextVitals,
  {
    rules: {
      // These effects intentionally sync React state with external systems
      // (localStorage portfolio store, lightweight-charts data, mount flags)
      // and mutate ref-held chart data buffers for live updates.
      // The new react-hooks heuristics flag them as false positives here.
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/immutability": "off",
    },
  },
];

export default config;
```

---

## STEP 5 — Revert to a clean tree

```
$ git checkout -- frontend/package.json frontend/package-lock.json
$ git status --porcelain
(no output for frontend/ — only the untracked STATE111-ESLINT.md remains)
```

`frontend/package.json` and `frontend/package-lock.json` are byte-identical to
base `9d447a3`. `node_modules` was restored with a fresh `npm ci`.

---

## STOP CONDITION — verbatim proof (restored baseline tree)

### `cd frontend && npm ci`

```
added 649 packages, and audited 650 packages in 1m

167 packages are looking for funding
  run `npm fund` for details

9 high severity vulnerabilities

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
npm ci EXIT=0
```

### `npm audit --audit-level=high`

Goal was 0 high. **Not achieved — 9 high, unchanged from base.** BLOCKED-UPSTREAM
per STEP 2 and STEP 3. Tail:

```
9 high severity vulnerabilities

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force
audit EXIT=1
```

(Full report identical to the STEP 2 baseline block above. All 9 findings are the
single GHSA-mh99 root advisory plus its `depends-on` cascade.)

### `npm run lint`

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

lint EXIT=0
```

0 errors, 0 warnings (`--max-warnings=0` preserved, rule set unchanged).

### `npm run typecheck`

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

typecheck EXIT=0
```

### `npm run build`

Captured as `npm run build 2>&1 | tail -18` (route table truncated to the tail by
that pipeline; 119 routes emitted in full):

```
├ ○ /traders                                     5.32 kB         121 kB
├ ƒ /traders/[name]                              4.61 kB         120 kB
├ ƒ /twitter-image                                 239 B         103 kB
├ ○ /usage                                       7.49 kB         172 kB
├ ● /w/[handle]                                  3.03 kB         119 kB
├   └ /w/demo
├ ○ /watchlist                                   6.19 kB         165 kB
└ ○ /weather                                     1.97 kB         114 kB
+ First Load JS shared by all                     103 kB
  ├ chunks/1255-f5767ca0d1da046a.js                46 kB
  ├ chunks/4bd1b696-100b9d70ed4e49c1.js          54.2 kB
  └ other shared chunks (total)                  2.73 kB


○  (Static)   prerendered as static content
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand

build EXIT=0
```

### `npm run test`

```
> alphaedge-frontend@0.1.0 test
> vitest run


 RUN  v4.1.8 E:/polymarket-worktrees/loop111-eslint10/frontend


 Test Files  101 passed (101)
      Tests  569 passed (569)
   Start at  07:57:26
   Duration  18.97s (transform 7.45s, setup 0ms, import 26.99s, tests 4.21s, environment 29ms)

test EXIT=0
```

Summary line: **`Test Files  101 passed (101)` / `Tests  569 passed (569)`** —
identical to the STATE107 baseline.

---

## Risk position (unchanged, re-affirmed)

`GHSA-mh99-v99m-4gvg` remains **ACCEPTED-RISK**, on the same reasoning recorded
in STATE107 and now with a stronger upstream-blocked justification:

- **Dev-only.** The chain is `eslint-config-next → eslint-plugin-{import,
  jsx-a11y,react} → minimatch@3 → brace-expansion@1.1.16`. It executes only
  during `npm run lint` / editor linting. Nothing from this chain enters the
  Next.js runtime bundle or server.
- **Not attacker-controlled.** The vulnerable code path is brace-glob expansion
  over lint patterns authored in this repo. Worst case is a self-inflicted OOM
  of a local lint process.
- **No non-destructive fix exists** as of 2026-07-25 (see STEP 2/3 evidence).

## Re-check trigger

Re-attempt when **any** of these ship:

1. `eslint-plugin-react` > 7.37.5, `eslint-plugin-jsx-a11y` > 6.10.2, or
   `eslint-plugin-import` > 2.32.0 with `minimatch` >= 9 **and** an eslint-10
   peer range — all three are required.
2. `eslint-config-next` publishing a release whose plugin set no longer reaches
   `minimatch@3`.
3. A `brace-expansion@1.1.17` backport of the GHSA-mh99 fix (would make the
   whole migration unnecessary).

Quick recheck command:

```
npm view eslint-plugin-react version && npm view eslint-plugin-react dependencies.minimatch
npm view eslint-plugin-jsx-a11y version && npm view eslint-plugin-jsx-a11y dependencies.minimatch
npm view eslint-plugin-import version && npm view eslint-plugin-import dependencies.minimatch
npm view brace-expansion versions --json | tail
```

## Files changed by this loop

- `STATE111-ESLINT.md` (this file) — added.
- Nothing else. `frontend/package.json`, `frontend/package-lock.json`,
  `frontend/eslint.config.mjs` and all source files are unmodified.

## AutoLab

```
AutoLab: baseline=npm audit --audit-level=high → 9 high (GHSA-mh99 cascade), lint/typecheck/build/test green | benchmark=count of high-severity findings from `npm audit --audit-level=high` | iterations=1 (eslint@9.39.4→10.8.0 + eslint-config-next@16.2.6→16.2.11: 9→6 high but `npm run lint` EXIT=2, TypeError in eslint-plugin-react@7.37.5 under eslint 10) | budget=1/2 retries used, stopped on a hard upstream blocker rather than spending the rest | outcome=retired — BLOCKED-UPSTREAM, reverted to the green baseline; never handed off worse than baseline
```
