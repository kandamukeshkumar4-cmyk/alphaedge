# STATE107 — Scanner Studio starter catalog

Node: `loop107-scanners` / branch `loop107-scanners/node`.
Problem: `GET /api/v1/scanners/` returned `200 []` in production, so Scanner
Studio was an empty main-nav surface on first run.

---

## 1. Schema / compile findings (file:line)

### Model

- `backend/app/db/models.py:1083` — `class Scanner`. Research-only by docstring
  (`:1084-1088`): stores universe/schedule/steps/delivery JSON, never touches
  RiskService / OrderBookService.
- `backend/app/db/models.py:1095` — `owner: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)`.
  **`owner` is nullable and is a free-form string, not a FK to `users`.** So a
  system/public identity already exists in the model: `owner=None`. No
  coordination needed, no migration needed.
- `backend/app/db/models.py:1099-1101` — `is_public`, `is_featured`,
  `cooldown_minutes`.
- No unique constraint on `Scanner.name`, so idempotency must be enforced by the
  seeder's own lookup (see §3), not by the database.

### "Public" semantics

- `backend/app/api/v1/scanners.py:213-225` — `list_scanners`. Anonymous callers
  (`user is None`) get `Scanner.is_public.is_(True)` only; authenticated callers
  additionally get their own rows. A seeded row therefore needs
  `is_public=True` to appear on the empty prod surface.
- `backend/app/api/v1/scanners.py:147-156` — `_get_visible_scanner`: public OR
  owned. With `owner=None` no real user can ever match `scanner.owner`, so the
  starters are read/run/fork-only for everyone and cannot be edited, paused, or
  deleted through the user-facing endpoints (`update`/`pause`/`resume`/`rollback`
  all require `scanner.owner == str(user.id)`, `:357-358`, `:470`, `:500`,
  `:520`). That is the desired behaviour for a system catalog.
- `backend/app/api/v1/scanners.py:396-414` — `run_scanner_now` allows a run when
  `scanner.is_public`, so any signed-in user can run a starter.
- `backend/app/api/v1/scanners.py:576-596` — `fork_scanner` copies the spec into
  a private draft owned by the caller. This is the "learn from working examples"
  path the catalog is for.
- `backend/app/api/v1/scanners.py:311-322` — `featured_scanners` lists
  `is_featured`. Seeded starters set `is_featured=True` so that surface is not
  empty either.

### Compile / validation

There is no separate "compile step" on write — `POST /scanners/` (`:171-210`)
only checks `spec.steps` is a list. The compiler module is the real authority:

- `backend/app/services/scanner_compiler_service.py:124` — `compile_scanner_spec`
  (NL → spec, keyword based, never raises).
- `backend/app/services/scanner_compiler_service.py:108-121` — `_default_spec()`
  defines the canonical spec shape: `name`, `universe.{categories,minimum_volume}`,
  `schedule.{timezone,market_hours_only,interval_minutes}`, `steps`,
  `delivery.{email,in_app,cooldown_minutes}`, `limit`, `notes`.
- `backend/app/services/scanner_compiler_service.py:219` —
  **`is_valid_compiled_spec`** is the whitelist/schema gate. It is the function
  the system itself uses to decide whether a spec is acceptable (LLM planner
  output must pass it before it can replace the deterministic spec, `:372` and
  `:383`). Constraints:
  - `:19-27` `_KNOWN_STEP_TYPES` = `WHALE_FLOW`, `PRICE_TREND`, `NEWS_SENTIMENT`,
    `MODEL_EDGE`, `DIRECTION_ALIGNMENT`. Nothing else is valid.
  - `:28` `_KNOWN_CATEGORIES` = `nba`, `sports`, `election`, `crypto`.
  - `:29-30` `5 <= schedule.interval_minutes <= 1440`.
- `backend/app/services/scanner_compiler_service.py:312` — `validate_spec`
  returns non-blocking warnings: `empty universe` (no categories),
  `no signal steps`, `cooldown less than interval`, and a spend warning for
  `interval < 15` with `> 3` steps.

**Consequence for authoring.** The brief's example themes map onto the whitelist
as follows, and the ones with no representable step were dropped rather than
faked:

| Brief theme | Representable? |
| --- | --- |
| big 24h price move | yes — `PRICE_TREND` with `window_days: 1` |
| whale-flow spike | yes — `WHALE_FLOW` |
| new-market surge / high volume | yes — `universe.minimum_volume` + `PRICE_TREND` |
| model-vs-market stretch | yes — `MODEL_EDGE` |
| news-confirmed move | yes — `NEWS_SENTIMENT` + `DIRECTION_ALIGNMENT` |
| cross-venue divergence | **no** — no venue-comparison step type exists |
| closing-soon (time-to-lock) | **no** — no time-to-lock filter exists in `universe` |

No step type was invented and no migration was added to make the missing two
work; that would have been extra scope. See §6.

### Run semantics

- `backend/app/services/scanner_executor_service.py:488` — `run_scanner`.
- `:75-93` `_load_universe`: `Market.status == OPEN`, category substring match
  against `category`/`slug`/`title` (`:44-56`), `volume >= minimum_volume`,
  truncated to `spec.limit`.
- `:575-588` an empty universe finishes the run with `status="empty"` and
  `error=None` — **an empty result is a legitimate, non-error outcome**, which is
  what the end-to-end test asserts against.
- `:673` otherwise `status` is `completed` / `empty`.
- No order path anywhere in the executor; it reads markets, candles, whale flow,
  news and the forecast service only.

### Seed precedent

- `backend/app/services/skill_seed_service.py:53` — `seed_default_skills`:
  loop over a module-level list, `select(...).where(Model.name == name)`, skip if
  present, `db.add(...)`, `flush()` once, return created count. `created_by=None`
  (`:71`) is the existing "system identity" convention.
- `backend/app/main.py:795-798` — the lifespan calls
  `seed_signal_events(session)` then `seed_default_skills(session)` inside the
  same session, followed by `await session.commit()`.

This is the mechanism followed exactly. There is no `scripts/` or
`app/db/seed` alternative in the repo for this class of data.

---

## 2. Seeded catalog (8 public starters)

All are `owner=None`, `is_public=True`, `is_featured=True`, `status="active"`,
`version=1`. Defined in
`backend/app/services/scanner_seed_service.py` → `STARTER_SCANNERS`.

| Name | One-liner | Steps | Universe |
| --- | --- | --- | --- |
| Big Mover Radar | Flags markets whose price moved sharply over the last day. | `PRICE_TREND(1d)` | all 4 categories |
| Whale Flow Watch | Surfaces markets where big paper-money flow is pushing hard in one direction. | `WHALE_FLOW` | all 4 categories |
| Model Edge Radar | Finds markets where our forecast model disagrees most with the current price. | `MODEL_EDGE` | all 4 categories |
| High-Volume Momentum | Tracks the busiest markets riding a clear multi-day price trend. | `PRICE_TREND(7d)` | all 4, `minimum_volume=25000` |
| News Pulse Confirmed | Watches fresh news sentiment and only keeps markets where price agrees. | `NEWS_SENTIMENT` → `PRICE_TREND(3d)` → `DIRECTION_ALIGNMENT` | all 4 categories |
| Triple Confirmation | Only fires when whale flow, price trend, and model edge all point the same way. | `WHALE_FLOW` → `PRICE_TREND(7d)` → `MODEL_EDGE` → `DIRECTION_ALIGNMENT` | all 4 categories |
| NBA Sharp Money | NBA-only: big paper-money flow that the recent price move agrees with. | `WHALE_FLOW` → `PRICE_TREND(1d)` → `DIRECTION_ALIGNMENT` | `nba` |
| Election Edge Watch | Election markets only: where our model price sits furthest from the market. | `MODEL_EDGE` | `election` |

Every entry is constructed through the `_spec()` helper
(`scanner_seed_service.py:24`, catalog list at `:62`) so it emits the exact `_default_spec()` shape,
and each sets `delivery.cooldown_minutes >= schedule.interval_minutes` so
`validate_spec()` returns `[]` (no warnings) — asserted by the test.

`delivery.email` is `False` on all eight: a system-owned scanner has no
recipient, and email delivery is a per-user opt-in concern.

---

## 3. Idempotency

`seed_starter_scanners` (`backend/app/services/scanner_seed_service.py:185`)
matches on `Scanner.name == name AND Scanner.owner IS NULL` and skips existing
rows. It is **insert-only** — it never updates an existing row, so a redeploy
cannot clobber an operator's edits (e.g. un-featuring or pausing a starter).
Returns the number of rows created; a second call returns `0`.

Matching on `owner IS NULL` (rather than name alone) means a user who names their
own scanner "Whale Flow Watch" does not suppress the system row, and the system
row does not collide with theirs.

---

## 4. Charter files touched

- `backend/app/services/scanner_seed_service.py` — new (the seed module).
- `backend/tests/test_loop107_scanner_seeds.py` — new (the four required tests).
- `STATE107-SCANNERS.md` — this file.
- `backend/app/main.py` — **exactly two lines**, appended at the end of the
  lifespan seed block, immediately after the existing `seed_default_skills`
  call:

  ```
  799:        from app.services.scanner_seed_service import seed_starter_scanners
  800:        await seed_starter_scanners(session)
  ```

  (Line numbers as of this branch; the pre-existing `seed_default_skills` call is
  at `797-798` and the shared `await session.commit()` follows.) A parallel node
  is also editing `main.py`; this diff is 2 added lines and touches nothing else.

- `backend/tests/test_heartbeat_guards.py` and
  `backend/tests/test_inprocess_scheduler.py` — **outside the stated charter,
  but required**: both drive the *real* `lifespan` against a minimal fake
  session and no-op every seed call individually
  (`monkeypatch.setattr("app.services.skill_seed_service.seed_default_skills", _noop)`).
  Adding the new hook made all four of their lifespan tests fail with
  `AttributeError: '_FakeSession' object has no attribute 'scalar'`. Fix is one
  added `monkeypatch.setattr` per test (3 lines each, 4 tests), directly below
  the existing `seed_default_skills` stub. No assertions or behaviour changed.

Not touched: `backend/app/api/v1/scanners.py` (no public-listing tweak was
needed — `list_scanners` already returns public rows to anonymous callers),
`app/alpha/**`, `opportunities.py`, `frontend/**`, `workers/tasks.py`.

**Zero migrations.** `Scanner.owner` is already nullable
(`app/db/models.py:1095`), so no schema change was required.

---

## 5. Guardrails

- `PAPER_TRADING_ONLY` untouched.
- Seeds emit alerts/signals only. No `RiskService`, no `OrderBookService`, no
  `OrderIntent` anywhere in the seed module or its tests.
- No LLM calls in the seed path — specs are literal dicts, never routed through
  `_llm_plan_spec`.
- No fabricated run results: seeding creates `Scanner` rows only, never
  `ScannerRun` rows. The end-to-end test executes a real run.
- No secrets printed or set. Nothing pushed or deployed.

---

## 6. NEEDS items

- **NEEDS COORDINATION: none for owner identity.** `Scanner.owner` is nullable
  (`app/db/models.py:1095`) and `owner=None` is the established system-identity
  convention (`skill_seed_service.py:71` uses `created_by=None`). The brief's
  fallback clause did not need to be exercised.
- **NEEDS PRODUCT DECISION: cross-venue divergence and closing-soon starters.**
  Both were in the brief's example list but are not expressible in the current
  spec DSL — there is no venue-comparison step type
  (`scanner_compiler_service.py:19-27`) and no time-to-lock filter in
  `universe` (`:108-121`). Adding either means a new step type in the compiler
  whitelist plus executor support, which is out of this loop's charter. Filed
  here rather than faked.
- **NEEDS OPS (observed, since self-resolved): disk pressure on `E:`.** The first
  full-suite attempt aborted with 22 `OSError: [Errno 28] No space left on
  device` errors; `E:` was at 100% (~325 MB free) with `E:\polymarket-worktrees`
  alone at 46.93 GB across ~80 worktrees. Space was reclaimed externally
  mid-loop (44 GB free by the final run), so the recorded gate output in §7 is
  from a clean disk. Worth watching: ~80 stale worktrees each carrying a
  ~0.5 GB `.venv` is the structural cause.

---

## 7. Verbatim gate output

### `cd backend && uv run --extra dev pytest -q tests/test_loop107_scanner_seeds.py --basetemp=E:/polymarket-worktrees/loop107-scanners/.pt`

```
....                                                                     [100%]
4 passed in 53.90s
```

### `cd backend && uv run --extra dev ruff check app tests`

```
All checks passed!
```

### `cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop107-scanners/.pt2`

```
...                                                                      [100%]
3 passed in 18.18s
```

### `cd backend && uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop107-scanners/.ptf`

Summary line (last line of the run; exit code 0, no `FAILED` or `ERROR` lines):

```
2118 passed, 28 skipped, 2 warnings in 1114.03s (0:18:34)
```

---

## 8. Commits

`git log --oneline` (this loop's commits sit on top of `67b380b`, the wave-105
tip; the earlier `e75423a` wip checkpoint was reshaped into the two commits
below):

```
fddb715 fix(loop107): stub the new scanner seed in lifespan tests
bc7f3a2 test(loop107): cover starter-scanner compile, idempotency, listing, run
372cdc3 feat(loop107): seed 8 public starter scanners at boot
67b380b docs(loop105): final prod smoke HEALTHY — wave 105 verified end to end
```

(The `docs(loop107)` commit adding this file is not shown above — it is created
by the same command that finalises this section.)

Nothing was pushed or deployed.
