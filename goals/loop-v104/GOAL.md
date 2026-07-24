# Wave V104 — Completion Sweep (graph)

Follows `.agents/skills/graph-design/SKILL.md`: parallel fan-out → sync barrier →
maker-checker tail → persist (+rejection reasons) → checkable stop.

## The diagram (drawn before any brief was written)

```
                    ┌─ N1 routes    (Sol,    xhigh)  traders/ + library/ dead routes
   fan-out ────────┼─ N2 social-be (Cursor, high)   social/watchlist API  ── FROZEN CONTRACT ──┐
   (4 nodes,        ├─ N3 a11y      (Qwen,   junior) axe sweep, 25 routes                       │
    disjoint        └─ N4 community (Luna,   xhigh)  stories/comments UI  ◄─────────────────────┘
    charters)                                          (builds against contract, NOT the server)

   parallel, no edges between N1..N4 — every "and then" was deleted as a fake edge.
   N2→N4 is a REAL data dependency, dissolved by freezing the contract up front
   so both run concurrently. That is the only cross-node dependency in the wave.

        │
        ▼
   N5 GAP MAP (Grok, read-only, runs concurrently) ──► input to wave V105, not a blocker
        │
        ▼
   SYNC BARRIER (orchestrator, zero agent tokens): collect STATE104.md from each node
        │
        ▼
   VERIFIER EDGE (Grok, different model than every author) — re-runs each node's own
   proofs + diffs its charter. Mandatory on N3 (Qwen) and N4 (Luna): both seats'
   known failure mode is claiming "done" before it is true.
        │
        ▼
   merge → gate → build → deploy → verify prod (fingerprint, not "Online")
```

## Node contracts

| node | seat | exclusive charter | stop condition (checkable, not self-claimed) |
|---|---|---|---|
| N1 routes | Sol xhigh | `app/traders/**`, `app/library/**`, `components/traders|library/**`, `lib/traders-api.ts`, `lib/library-api.ts`, `api/v1/track_record.py` | typecheck+lint+build clean, `e2e/traders.spec.ts` + `e2e/library.spec.ts` green |
| N2 social-be | Cursor 4.5 high | `alembic/065_social_community.py`, `models/social.py`, `services/social_service.py`, `api/v1/social.py`, `api/v1/watchlist.py`, `tests/test_loop104_social.py` | 10 named tests green, authz matrix green, openapi snapshot regenerated, full suite green |
| N3 a11y | Qwen3.8 Max | `e2e/a11y.spec.ts` + `src/**` minus other nodes' dirs | axe: 0 serious/critical over 25 routes, typecheck+lint+build |
| N4 community | Luna xhigh | `lib/social-api.ts`, `components/community/**`, `app/community/**`, `app/w/[handle]/**`, `e2e/community.spec.ts` | typecheck+lint+build clean, `e2e/community.spec.ts` green |
| N5 gap map | Grok (read-only) | `GAPMAP104.md` only | file exists with evidence-cited verdict table |

## Migration ownership
N2 owns **065** (parent 064) and it is the **only** migration in the wave. N1/N3/N4 own
zero — a "NEEDS MIGRATION" note in STATE104.md is the correct escape hatch. This is the
V86 multiple-heads lesson encoded as a brief-level rule.

## Guardrails carried into every brief
PAPER_TRADING_ONLY stays true; no node may create an order path (RiskService →
OrderIntent → OrderBookService remains the only one, and none of these nodes touch it).
Comment text is untrusted input: server-capped, rendered as plain text, never fed to an
LLM as instructions. No secrets printed or set by any node. No node pushes or deploys —
the orchestrator reviews, merges, deploys.

## Budget law
Per node: 2 retries per failing command, 3 strikes on one error → ESCALATION + STOP.
Extra scope is a defect: out-of-charter findings are listed in STATE104.md, not fixed.
