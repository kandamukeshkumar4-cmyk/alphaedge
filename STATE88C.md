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

`git log -1` for the V1 commit is appended in the V2 section below.
