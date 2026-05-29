# AlphaEdge Week 1 Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify the first reviewable AlphaEdge base: paper-trading NBA CLOB, market lifecycle APIs, event logging, Docker services, CI, and task handoff docs.

**Architecture:** FastAPI owns admin/public routes and delegates market lifecycle and matching to domain services. SQLAlchemy/Alembic persists accounts, markets, orders, fills, positions, ledger entries, and domain events. Later-week modules can exist as scaffold, but the first PR must only claim Week 1 behavior unless additional gates are verified.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Postgres, Redis, pytest, Ruff, Next.js 15, GitHub Actions.

---

## File Structure

- `README.md`: portfolio positioning, paper-trading disclaimer, quick start, canonical Lakers/Celtics example.
- `AGENTS.md`: repo-specific Codex/Cursor operating rules and verification gates.
- `.github/workflows/ci.yml`: backend and frontend CI checks.
- `.github/pull_request_template.md`: PR claim and verification checklist.
- `.github/ISSUE_TEMPLATE/cursor-task.yml`: structured task format for Cursor execution.
- `docs/project/CURSOR_2_5_TASKS.md`: executor task board.
- `docker-compose.yml`: Postgres, Redis, and API for Week 1; worker remains profile-gated.
- `backend/app/market/order_book.py`: in-memory price-time priority matching engine.
- `backend/app/services/order_book_service.py`: persisted order submission, fill recording, position/cash mutation, domain events.
- `backend/app/services/market_service.py`: create, lock, resolve, seed system account, settlement.
- `backend/tests/test_orderbook_lakers_celtics.py`: canonical integration test.
- `frontend/eslint.config.mjs`: non-interactive ESLint config for CI.

## Task 1: Verify Week 1 CLOB Behavior

**Files:**
- Test: `backend/tests/test_orderbook_lakers_celtics.py`
- Test: `backend/tests/test_orderbook_engine.py`
- Modify only if failing: `backend/app/market/order_book.py`
- Modify only if failing: `backend/app/services/order_book_service.py`
- Modify only if failing: `backend/app/services/market_service.py`

- [ ] **Step 1: Run the canonical tests**

Run from `E:\polymarket clone\backend`:

```powershell
uv run --extra dev pytest tests/test_orderbook_lakers_celtics.py tests/test_orderbook_engine.py -q
```

Expected: both tests pass. If the result fails, capture the exact failing assertion before editing code.

- [ ] **Step 2: Confirm price-time priority**

Read `backend/tests/test_orderbook_lakers_celtics.py` and confirm this exact behavior remains covered:

```python
assert matches[0].sell_order_id == oid1
assert matches[1].sell_order_id == oid2
```

Expected: same-price resting sell orders fill in insertion order.

- [ ] **Step 3: Confirm settlement semantics**

Read the same test and confirm these exact checks remain covered:

```python
assert taker.cash_balance == Decimal("5045.00") or taker.cash_balance == Decimal("5045")
assert maker.cash_balance >= Decimal("5055")
```

Expected: Lakers win resolves YES at `$1`, and the buyer receives settlement credit after paying fill cost.

- [ ] **Step 4: Commit only after verification**

```powershell
git add backend/app/market/order_book.py backend/app/services/order_book_service.py backend/app/services/market_service.py backend/tests/test_orderbook_lakers_celtics.py backend/tests/test_orderbook_engine.py
git commit -m "feat: add week 1 order book base"
```

Expected: commit is created only if the task changed these files and tests pass.

## Task 2: Verify API, Security, and Events

**Files:**
- Test or inspect: `backend/app/admin/routes.py`
- Test or inspect: `backend/app/api/v1/routes.py`
- Test or inspect: `backend/app/events/bus.py`
- Test or inspect: `backend/app/core/security.py`
- Modify only if failing: `backend/tests/`

- [ ] **Step 1: Inspect admin dependency**

Confirm admin routes use:

```python
Depends(verify_admin_api_key)
```

Expected: create, lock, resolve, and seed routes require the admin API key header.

- [ ] **Step 2: Inspect event emission**

Confirm market and order services emit these event names:

```text
market_created
market_locked
market_resolved
order_submitted
order_filled
```

Expected: events persist through `DomainEventBus.emit()`.

- [ ] **Step 3: Run the full backend test suite**

Run from `E:\polymarket clone\backend`:

```powershell
uv run --extra dev pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Run Ruff**

Run from `E:\polymarket clone\backend`:

```powershell
uv run --extra dev ruff check app tests
```

Expected: no lint errors.

## Task 3: Verify Frontend Scaffold Without Claiming Week 4

**Files:**
- `frontend/src/app/page.tsx`
- `frontend/src/app/admin/page.tsx`
- `frontend/src/app/eval/page.tsx`
- `frontend/src/app/markets/page.tsx`
- `frontend/eslint.config.mjs`
- `frontend/package.json`

- [ ] **Step 1: Run ESLint**

Run from `E:\polymarket clone\frontend`:

```powershell
npm run lint
```

Expected: command exits without an interactive prompt and without warnings.

- [ ] **Step 2: Run typecheck**

```powershell
npm run typecheck
```

Expected: TypeScript exits cleanly.

- [ ] **Step 3: Build**

```powershell
npm run build
```

Expected: Next.js production build succeeds.

- [ ] **Step 4: Keep PR language scoped**

Use this exact PR wording for frontend until Week 4 is verified:

```text
Includes a minimal Next.js scaffold for later admin/proof dashboard work. This PR does not claim the Week 4 dashboard gate.
```

## Task 4: Prepare GitHub Handoff

**Files:**
- `.github/workflows/ci.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/cursor-task.yml`
- `docs/project/CURSOR_2_5_TASKS.md`

- [ ] **Step 1: Confirm working tree**

Run from `E:\polymarket clone`:

```powershell
git status --short
```

Expected: only intended source, docs, fixture, and lockfile changes are listed.

- [ ] **Step 2: Create branch**

```powershell
git switch -c codex/alphaedge-base
```

Expected: branch is `codex/alphaedge-base`.

- [ ] **Step 3: Create remote repo**

```powershell
gh repo create kandamukeshkumar4-cmyk/alphaedge --public --source . --remote origin --description "Paper-trading NBA prediction market simulation with CLOB, evaluation, risk, and agent scaffolding"
```

Expected: `git remote -v` shows `origin` pointing at `https://github.com/kandamukeshkumar4-cmyk/alphaedge.git`.

- [ ] **Step 4: Push branch**

```powershell
git push -u origin codex/alphaedge-base
```

Expected: branch exists on GitHub and CI starts.

## Self-Review

- Spec coverage: Week 1 CLOB/API/events/security, repo setup, Cursor task assignment, and CI are covered.
- Scope correction: Existing Week 2-4 scaffold is allowed to remain, but task language prevents false claims that those gates are complete.
- Placeholder scan: no `TBD`, `TODO`, or vague "add tests" steps remain.
- Type consistency: `OrderIntent`, `RiskService`, `OrderBookService`, `MarketService`, and route file names match the current repo.
