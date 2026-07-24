# STATE104 — loop104-social backend node

Branch: `loop104-social/node`  
Base: `9bfa413`  
Seat: Cursor Grok 4.5 High (BACKEND)

## Delivered (charter only)

1. `backend/alembic/versions/065_social_community.py` — tables `story_comments`, `story_reactions`, `watchlist_shares` (`down_revision=064_alpha_runs`)
2. `backend/app/models/social.py` — `StoryComment`, `StoryReaction`, `WatchlistShare`
3. `backend/app/services/social_service.py` — exact signatures; stories derived from `PaperOrder` + `Watchlist` (no stories table)
4. `backend/app/api/v1/social.py` — 5 community routes on existing router
5. `backend/app/api/v1/watchlist.py` — 2 share routes on existing router
6. `backend/tests/test_loop104_social.py` — 10 exact contract tests
7. `backend/tests/test_loop26_authz_matrix.py` — AUTH_CLASS + totals bumped (209 paths / 230 ops / public=115 / user=70)
8. OpenAPI snapshot regenerated (required by stop condition)

## Guardrails

- No RiskService / OrderBookService imports in social code
- Comment body capped 1..500 after strip; plain text only
- `PAPER_TRADING_ONLY` untouched
- AutoLab: not applicable (no iterative measure)

## Outside charter (listed, not fixed)

- Untracked `cursor-prompt.txt`, `cursor104.log`, `cursor104-fullsuite.log` (local run artifacts)
- Models package is new (`app/models/`) while most ORM still lives in `app/db/models.py` — charter-required path

---

## Proof commands (pasted)

### 1) Targeted pytest

```text
cd backend && uv run --extra dev pytest -q tests/test_loop104_social.py tests/test_loop26_authz_matrix.py --basetemp=E:/polymarket-worktrees/loop104-social/.pt
............                                                             [100%]
12 passed in 59.67s
```

### 2) OpenAPI snapshot regen

```text
cd backend && uv run python scripts/regen_openapi_snapshot.py
wrote E:\polymarket-worktrees\loop104-social\backend\tests\fixtures\openapi_snapshot.json (209 paths)
```

### 3) Ruff

```text
cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### 4) Full suite

```text
cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop104-social/.ptf
2091 passed, 28 skipped in 647.89s (0:10:47)
```

---

## git log --oneline

```text
665ec87 feat(loop104): cover social contract and authz matrix surface
e8ff7fb feat(loop104): add community stories, reactions, and shared watchlists
49bda4d feat(loop104): add social community migration and models
9bfa413 merge(loop102): alpha runs/signal/hypotheses UI (Qwen, Grok rubric-PASS)
00623cf feat(loop102): AR3 — proposed hypotheses section + alpha-runs E2E
65a034f merge(loop103): PWA manifest + SEO/launch meta (Cursor; service worker skipped — no caching next to live prices)
38713dc feat(loop103): P3 — PWA e2e + skip service worker (stale-data risk)
34b8d5f feat(loop102): AR2 — latest-signal hero + run history on /alpha
```


## Blocker fix

Auditor blocker: unstable story cursor under equal `created_at` (composite `(created_at, id)` + tuple filter).

### 1) Targeted pytest (11 tests)

```text
cd backend && uv run --extra dev pytest -q tests/test_loop104_social.py --basetemp=E:/polymarket-worktrees/loop104-social/.ptfix
...........                                                              [100%]
11 passed in 24.86s
```

### 2) Ruff

```text
cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### 3) OpenAPI contract shape

Verified live `StoryPageOut` still `{items, next_cursor: str|null}`; path count 209 == snapshot. No regen required (opaque cursor string only; response shape unchanged).

## Noted, not fixed

- Reaction concurrent double-POST can still 500 without IntegrityError handling (auditor non-blocking).
- GET stories uses `get_optional_user` while AUTH_CLASS says `"public"` — behavior OK (auditor nit).
- `profile_public` filter on story derivation undocumented in frozen contract.
- `_resolve_user_by_handle` loads all users then filters in Python.
- `app.models.social` not wired into alembic/env.py / conftest import graph.
- Kinds `forecast` / `note` allowed by schema, never produced by current derivation.
