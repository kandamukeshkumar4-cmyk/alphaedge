# Loop V83 — Skills Gallery UI (frontend worktree)

Charter surface: `frontend/**` and `STATE83.md` only. One commit per ticket
(`feat(loop83): S<n> — ...`). Verify per ticket: `npm run typecheck &&
npm run lint`. End: `npm run build` + `npx vitest run` + `e2e/skills.spec.ts`.

| Ticket | Status | Proof |
| --- | --- | --- |
| S1 | DONE | `frontend/src/lib/skills-api.ts` (list/get/run + save-as-skill, live-first mock fallback). `frontend/src/lib/terminal-api.ts` `seedMockTerminalSession` helper. `npm run test -- src/lib/skills-api.test.ts` → 3/3 pass (shape, run returns session id, fallback). typecheck + lint clean. |
| S2 | DONE | `frontend/src/app/skills/{page,layout}.tsx` + `frontend/src/components/skills/{SkillCard,SkillsGallery}.tsx` (grid, skeleton shimmer, empty state, hover lift, 40ms stagger via `t-rise`+`t-stagger-N`, reduced-motion kill). Run → `runSkill` → `router.push('/terminal?session={id}')`. typecheck + lint clean. |
| S3 | DONE | Composer Skills chip (`data-testid=terminal-skills-chip`) lists top 5 skills from `skills-api` with Run (`runSkillFromPopover`). `TerminalShell` reads `?session=` deep link. `TerminalSaveAsSkill` mini-form → POST `save-as-skill` → branded mint toast (never danger-red). typecheck + lint clean. |
| S4 | DONE | `SiteHeader` NAV adds `{Skills,/skills}`. Terminal sidebar Skills group header links to `/skills`. typecheck + lint clean. |

## Final verification (end gate)

- `npm run build` → PASS (`/skills` 3.68 kB, `/terminal` 15.5 kB; no errors).
- `npx vitest run` → 517 passed / 1 failed (91 files). The single failure is
  `terminal-api.test.ts > exposes six sense chips`, which asserts a
  `SENSE_CHIPS` order (`odds` first) that does **not** match the documented
  UI-DIRECTION order in source (`whale, news, sentiment, model, odds, arb`).
  Verified pre-existing: `git show HEAD~4:frontend/src/lib/terminal-api.ts`
  shows the same source order before any S1–S4 commit; S1 only added the
  `seedMockTerminalSession` helper (26 lines, no `SENSE_CHIPS` change). This
  failure predates and is unrelated to V83 — left untouched per the surgical
  rule. New `skills-api.test.ts` is among the 90 passing files.
- `npx playwright test e2e/skills.spec.ts --project=chromium` → 2/2 PASS
  (gallery renders skill cards from the mock catalog; Run navigates to
  `/terminal?session=…` and `terminal-page` is visible).

AutoLab: not applicable (no iterative measure — UI feature, verified by build + DOM-assertion e2e).

S1–S4 DONE. STOP. No push.
