# Loop V66 — Wave 10 docs (docs only)

> Runner: docs-only worktree `loop66/wave10-docs`. Exclusive charter below.
> **Never** app code, secrets, push, or merge.

## Outcome

Document the Wave 10 ship set with **real merge SHAs** only (from
`git log --oneline --merges -15` and verified `git show`). Every claim cites a
SHA. No fabricated features.

## Ownership (exclusive)

| Path | Ticket |
|------|--------|
| `CHANGELOG.md` | Wave 10 section |
| `docs/releases/wave-10.md` | Full release narrative |
| `docs/operations.md` | New loops: `pod_runner`, `heartbeat_manager`, `whale_flow`, `venue_gap` |
| `docs/user-guide.md` | `/pods` usage |
| `goals/loop-v66-wave10-docs/**` | GOAL + STATE |

## Wave 10 topics (must cover)

| Loop | Topic | Primary merge / land SHA (verify live) |
|------|--------|----------------------------------------|
| V56 | Lock provenance | `ffedfa4` |
| V58 | Whale flow + venue gaps + market context API | `4f9cb97` |
| V59 | Heartbeat manager | landed via `09af5eb` / `91239e3` (no titled merge(loop59)) |
| V57 | Pods engine (3 paper pods, scoring) | `40aeeec` |
| V60 | `/pods` UI | `8ae25a4` |
| V54 | QA e2e specs | `04162bc` |
| V61 | Sentiment desk (flag-gated; integration merge) | `ea2be72` |

## Tickets (one commit per file)

```text
docs(loop66): GOAL.md
docs(loop66): CHANGELOG.md
docs(loop66): wave-10.md
docs(loop66): operations.md
docs(loop66): user-guide.md
docs(loop66): STATE.md   # DONE + verification appendix, then STOP
```

## Evidence commands

```text
git log --oneline --merges -15
git show --stat <sha>
```

## Non-goals

- No backend/frontend code changes
- No secret values
- No push, no merge, no PR mutation
- Do not invent SHAs; if a loop has no titled merge, say so and cite the real land commits
