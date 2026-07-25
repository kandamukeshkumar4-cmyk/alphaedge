# STATE107-NPMSEC — frontend npm high-severity advisory triage & remediation

Worktree: `E:/polymarket-worktrees/loop107-npmsec` (branch `loop107-npmsec/node`, base `67b380b`).
Charter respected: only `frontend/package.json`, `frontend/package-lock.json`, and this file changed. Zero source-code changes. PAPER_TRADING_ONLY untouched. No push, no deploy.

## STEP 1 — Enumeration (verbatim `npm audit --audit-level=high` at baseline, after `npm ci` in fresh worktree)

```
# npm audit report

brace-expansion  <=5.0.7
Severity: high
brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups - https://github.com/advisories/GHSA-3jxr-9vmj-r5cp
brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups - https://github.com/advisories/GHSA-3jxr-9vmj-r5cp
brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash - https://github.com/advisories/GHSA-mh99-v99m-4gvg
fix available via `npm audit fix`
node_modules/@typescript-eslint/typescript-estree/node_modules/brace-expansion
node_modules/brace-expansion

js-yaml  4.0.0 - 4.2.0
Severity: high
JS-YAML: Quadratic-complexity DoS in merge key handling via repeated aliases - https://github.com/advisories/GHSA-h67p-54hq-rp68
js-yaml: YAML merge-key chains can force quadratic CPU consumption - https://github.com/advisories/GHSA-52cp-r559-cp3m
fix available via `npm audit fix`
node_modules/js-yaml

next  >=9.3.4-canary.0
Severity: high
Next.js: Denial of Service in App Router using Server Actions - https://github.com/advisories/GHSA-m99w-x7hq-7vfj
Next.js: Server-Side Request Forgery in Server Actions on custom servers - https://github.com/advisories/GHSA-89xv-2m56-2m9x
Next.js: Cache confusion of response bodies for requests with bodies - https://github.com/advisories/GHSA-68g3-v927-f742
Next.js: Cache confusion of response bodies for requests with bodies containing invalid UTF-8 byte sequences - https://github.com/advisories/GHSA-4633-3j49-mh5q
Next.js: Unbounded Server Action payload in Edge runtime - https://github.com/advisories/GHSA-4c39-4ccg-62r3
Next.js: Server-Side Request Forgery in rewrites via attacker-controlled destination hostname - https://github.com/advisories/GHSA-p9j2-gv94-2wf4
Next.js: Denial of Service in the Image Optimization API using SVGs - https://github.com/advisories/GHSA-q8wf-6r8g-63ch
Next.js: Unauthenticated disclosure of internal Server Function endpoints - https://github.com/advisories/GHSA-955p-x3mx-jcvp
Depends on vulnerable versions of postcss
Depends on vulnerable versions of sharp
fix available via `npm audit fix`
node_modules/next

postcss  <=8.5.17
Severity: high
PostCSS: Path Traversal in Previous Source Map Auto-Loading (sourceMappingURL) leads to Arbitrary .map File Disclosure - https://github.com/advisories/GHSA-r28c-9q8g-f849
fix available via `npm audit fix`
node_modules/postcss

sharp  <0.35.0
Severity: high
sharp inherited vulnerabilities in libvips: CVE-2026-33327, CVE-2026-33328, CVE-2026-35590, CVE-2026-35591 - https://github.com/advisories/GHSA-f88m-g3jw-g9cj
fix available via `npm audit fix`
node_modules/sharp

5 high severity vulnerabilities
```

### Per-advisory triage

| # | Package | Installed | Path | Advisories | Vulnerable range | Reachability |
|---|---|---|---|---|---|---|
| 1 | brace-expansion | 1.1.15 + 5.0.6 | Transitive, dev-only: eslint -> minimatch@3.1.5 -> brace-expansion@1.x; eslint-config-next -> typescript-eslint -> @typescript-eslint/typescript-estree -> minimatch@10.2.5 -> brace-expansion@5.x | GHSA-3jxr-9vmj-r5cp, GHSA-mh99-v99m-4gvg | <=5.0.7 | BUILD-TOOL-ONLY. Only reachable through `npm run lint` glob expansion on repo-controlled patterns; never shipped to the browser or the Next server runtime. DoS requires an attacker-controlled brace pattern; lint globs come from repo config. |
| 2 | js-yaml | 4.1.1 | Transitive, dev-only: eslint -> @eslint/eslintrc -> js-yaml | GHSA-h67p-54hq-rp68, GHSA-52cp-r559-cp3m | 4.0.0 - 4.2.0 | BUILD-TOOL-ONLY. Parses eslint YAML config (repo-controlled). Not in the runtime bundle. |
| 3 | next | 15.5.18 | Direct dependency (`^15.1.0`) | 8 advisories incl. SSRF in Server Actions/rewrites, cache confusion, DoS, Server Function endpoint disclosure | >=9.3.4-canary.0 (fixed in 15.5.19+ line) | RUNTIME-REACHABLE. next is the production server/framework; App Router, rewrites, and image optimizer are all in use. Highest-priority item. |
| 4 | postcss | 8.5.15 | Direct devDependency (`^8.5.15`) + pinned tree-wide via existing `overrides: { "postcss": "$postcss" }`; consumed by tailwindcss, autoprefixer, next, vite | GHSA-r28c-9q8g-f849 (path traversal via sourceMappingURL -> .map disclosure) | <=8.5.17 | BUILD-TOOL-ONLY. postcss runs at build time on repo CSS; the traversal needs a malicious sourceMappingURL in processed CSS. Not attacker-reachable at runtime, but trivially fixable. |
| 5 | sharp | 0.34.5 | Transitive: next optionalDependency `^0.34.3` | GHSA-f88m-g3jw-g9cj (libvips CVE-2026-33327/33328/35590/35591) | <0.35.0 | RUNTIME-REACHABLE (conditional). sharp is next's image-optimization backend when self-hosting (`next start` / Railway-style hosts). On Vercel the platform optimizer is used, but self-hosted runs would decode untrusted images through vulnerable libvips. Treated as runtime. |

## STEP 2 — Remediation (one commit per advisory, no `npm audit fix --force` used anywhere)

1. **brace-expansion** — `npm update brace-expansion`: 1.1.15 -> 1.1.16 (fixes GHSA-3jxr in the 1.x line) and 5.0.6 -> 5.0.8 (fixes both in the 5.x line). Commit `97f7967`.
   - Residual: GHSA-mh99-v99m-4gvg has **no fixed release in the 1.x line** (fix only in 5.0.8; minimatch@3 requires `^1.1.7`). See ACCEPTED-RISK below.
2. **js-yaml** — `npm update js-yaml`: 4.1.1 -> 4.3.0 (in-range for @eslint/eslintrc `^4.1.0`; 4.3.0 is the patched 4.x release). Commit `e24276c`.
3. **postcss** — `npm update postcss`: 8.5.15 -> 8.5.23 everywhere (in-range for the direct `^8.5.15` and propagated by the pre-existing `postcss: "$postcss"` override, so next/tailwind/vite all dedupe to 8.5.23). Commit `eedaf7a`.
4. **next** — `npm update next`: 15.5.18 -> 15.5.21 (patch-level, within `^15.1.0`; clears all 8 Next advisories). Commit `22bce8e`.
5. **sharp** — added `"sharp": "^0.35.0"` to `overrides` in `frontend/package.json`: 0.34.5 -> 0.35.3. Commit `2f32525`.
   - **Out-of-range pin justification (required):** next@15.5.21 still declares optionalDependency `sharp@^0.34.3`; there is no patched 0.34.x (advisory fixed only in >=0.35.0). The npm-suggested non-override "fix" was a breaking downgrade to next@14.2.35 — rejected. 0.34 -> 0.35 is a libvips-refresh minor for sharp; next consumes sharp's stable high-level pipeline API. Compatibility proven below by a full green `next build` (image pipeline exercised, 119 static pages) and the vitest suite.
6. Commit `bc687f0` is a no-version-change lockfile re-hoist (npm moved brace-expansion@5.0.8 to top level and nested 1.1.16 under minimatch after an override experiment was reverted; all resolved versions identical).

### Attempted and rejected (evidence-based)

- **Global override `"brace-expansion": "^5.0.8"`** would have driven audit to `found 0 vulnerabilities`, but brace-expansion 5.x exports `{ expand }` (named) while minimatch@3 does `expand = require('brace-expansion'); expand(pattern)`. Verified breakage — `npm run lint` crashed:
  ```
  TypeError: expand is not a function
      at Minimatch.braceExpand (...\node_modules\minimatch\minimatch.js:271:10)
      ...
      at FlatConfigArray.forEach (<anonymous>)
  ```
  Override reverted per "do not break the app". No `--force` used.

### ACCEPTED-RISK (1 root advisory, reported by npm as 9 findings via depends-on cascade)

- **brace-expansion@1.1.16 / GHSA-mh99-v99m-4gvg (DoS, unbounded expansion OOM)** under `eslint -> minimatch@3.1.5`. npm's only offered fix is `eslint@10.8.0` — a **major, breaking** bump (also drags eslint-config-next compatibility). The other 8 reported "high" findings are the same root advisory cascaded onto minimatch, @eslint/config-array, @eslint/eslintrc, eslint, eslint-plugin-import, eslint-plugin-jsx-a11y, eslint-plugin-react, eslint-config-next ("depends on vulnerable versions of ...").
  - Reachability: dev-only lint chain. The vulnerable code runs only when minimatch expands a brace glob during `npm run lint`/editor linting; patterns are authored in this repo, not attacker-controlled. Nothing from this chain ships in the runtime bundle or Next server. Worst case is a self-inflicted OOM of a local lint process.
  - Upgrade path: bump `eslint` to 10.x together with a compatible `eslint-config-next` (its eslint-10 line moves the chain to minimatch@10 + brace-expansion@5.0.8). That is a coordinated tooling migration (flat-config/major-API churn), not a security hotfix; deliberately out of scope for this conservative pass.

## STEP 3 — Proof (verbatim)

Environment note (auditor): mid-task the E: volume was driven to 0 bytes free by writers outside this worktree (`df: E: 100G 100G 0 100%`); `npm run build` hit `ENOSPC` twice during that window. Per charter, no other worktree was touched. After ops reclaimed 26+ GB, the entire proof set below was re-run natively (fresh `npm ci`, no junctions/workarounds) — all outputs below are from that final native run.

### `npm ci`

```
added 649 packages, and audited 650 packages in 9m

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

### `npm audit --audit-level=high` (final)

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

To address issues that do not require attention, run:
  npm audit fix

To address all issues (including breaking changes), run:
  npm audit fix --force
audit EXIT=1
```

All 9 findings are the single ACCEPTED-RISK root advisory (GHSA-mh99 on the dev-only eslint/minimatch@3 chain) plus its depends-on cascade. The original 5 root advisories: 4 fixed, 1 accepted with no non-breaking fix available.

### `npm run typecheck`

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

typecheck EXIT=0
```

### `npm run lint`

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

lint EXIT=0
```

### `npm run build`

```
> alphaedge-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.21

   Creating an optimized production build ...
 ✓ Compiled successfully in 2.7min
   Linting and checking validity of types ...
   Collecting page data ...
 ⚠ Using edge runtime on a page currently disables static generation for that page
   Generating static pages (0/119) ...
 ✓ Generating static pages (119/119)
   Finalizing page optimization ...
   Collecting build traces ...
[full route table emitted: 119 pages, First Load JS shared 103 kB]
build EXIT=0
```

### `npm run test` (vitest)

```
> alphaedge-frontend@0.1.0 test
> vitest run

 RUN  v4.1.8 E:/polymarket-worktrees/loop107-npmsec/frontend

 Test Files  101 passed (101)
      Tests  569 passed (569)
   Start at  22:23:59
   Duration  62.39s (transform 6.09s, setup 0ms, import 52.24s, tests 6.49s, environment 26ms)

test EXIT=0
```

## git log --oneline

```
# (as of this file's writing; the commit adding this STATE file follows bc687f0)
bc687f0 chore(loop107): security — lockfile rehoist after override round-trip (same versions)
2f32525 chore(loop107): security — sharp 0.34.5->0.35.3 (override)
22bce8e chore(loop107): security — next 15.5.18->15.5.21
eedaf7a chore(loop107): security — postcss 8.5.15->8.5.23
e24276c chore(loop107): security — js-yaml 4.1.1->4.3.0
97f7967 chore(loop107): security — brace-expansion 1.1.15->1.1.16, 5.0.6->5.0.8
67b380b docs(loop105): final prod smoke HEALTHY — wave 105 verified end to end
```
