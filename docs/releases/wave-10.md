# Wave 10 — Pods fleet, market context, heartbeat, provenance

**Date:** 2026-07-17  
**Scope:** per-lock forecast provenance, master market-context pipeline (whale
flow + venue gaps), code-only position heartbeat, multi-pod paper engine +
`/pods` command center UI, QA e2e honesty specs, and a flag-gated continuous
sentiment desk.

**Rules for this page:** every product claim cites a real git SHA from this
repo. No fabricated features, no secret values, paper-trading only.

Evidence basis (Loop V66):

```text
git log --oneline --merges -15
git show --stat <sha>
```

Primary merge / land SHAs used below:

| Topic | SHA | Subject |
|---|---|---|
| V56 | `ffedfa4` | `merge(loop56): per-lock forecast provenance — 048, same-transaction, honest nulls` |
| head integrate | `133af64` | `merge: integrate 048_lock_provenance head (unblocks ESCALATION)` |
| V58 | `4f9cb97` | `merge(loop58): master data pipeline — whale flow, venue gaps, market context, graph wiring` |
| heartbeat chain | `91239e3` | `fix(migrations): renumber heartbeat 051->052, chain onto 051_venue_gaps (single head)` |
| V59 config land | `09af5eb` | `fix(merge): resolve loop59 config.py conflict — union of V58 whale/gap + V59 heartbeat settings` |
| V57 | `40aeeec` | `merge-resolve(loop57): union loop registrations; re-chain 053_pods onto 052_heartbeat` |
| V60 | `8ae25a4` | `merge(loop60): pods command center UI — fleet dashboard, decision terminal, context panels` |
| V54 | `04162bc` | `merge(loop54): QA e2e specs — locked-forecast, bell/eval, resolved-count contract` |
| V61 | `ea2be72` | `merge(loop61): continuous sentiment desk — adaptive cadence, trend features, analyst lenses (flag-gated)` |

---

## V56 — Per-lock forecast provenance

### What shipped

Merge:

- `ffedfa4` — `merge(loop56): per-lock forecast provenance — 048, same-transaction, honest nulls`

Integration of the migration head onto the shared line:

- `133af64` — `merge: integrate 048_lock_provenance head (unblocks ESCALATION)`

Ticket path:

| Ticket | SHA | Summary |
|--------|-----|---------|
| P1 | `f58a1c1` | `048_lock_provenance` nullable provenance columns on `forecast_logs` |
| P2 | `45e977a` | Record honest per-lock provenance in the **same** lock transaction |
| P3 | `4dccbdb` | Surface `provenance_cutoff` in A/B preflight population summary |
| P4 | `9ca6980` | Provenance tests + gate counts in STATE |

### Why it matters to a user

“Model locked at X%” is only useful if we know **which producer path** wrote
that lock. Historic rows without provenance stay **null** — no backfill
invention. A/B readiness can disclose a provenance cutoff instead of silently
mixing unprovenanced history.

### Honesty constraints

- Same-transaction write with the lock (no orphan provenance).
- No `UPDATE` backfill of old rows (`ffedfa4` narrative: honest nulls).
- Does not change the RiskService → OrderIntent → OrderBookService path.

---

## V58 — Whale flow, venue gaps, market context API

### What shipped

Merge:

- `4f9cb97` — `merge(loop58): master data pipeline — whale flow, venue gaps, market context, graph wiring`

Tickets:

| Ticket | SHA | Summary |
|--------|-----|---------|
| D1 | `a1e5e96` | Whale flow — large-trade tape, `whale_events`, pressure |
| D2 | `1d7f114` | Cross-venue gap — store gaps + top-gaps API |
| D3 | `b88de74` | Master context API — market context + fleet digest |
| D4 | `bf119dd` | Wire `whale_pressure` + `venue_gap` into prediction graph |
| D5 | `2f882dd` | Tests + gate + STATE |

### Loops / APIs (ops-facing)

| Loop name | Role | Cadence (code) |
|-----------|------|----------------|
| `whale_flow` | Large-trade tape → whale pressure | ~60s (`WHALE_FLOW_INTERVAL_SEC`) |
| `venue_gap` | Polymarket vs Kalshi implied gap store | ~60s (`VENUE_GAP_INTERVAL_SEC`) |

Public surfaces introduced on this merge line (names only):

- `GET /api/v1/markets/{slug}/context` — master market context
- `GET /api/v1/context/digest` — fleet digest
- `GET /api/v1/venue-gaps` — top gaps
- Graph features remain flag-gated (`WHALE_SIGNAL_ENABLED` default false in
  loop STATE for D4)

Both loops are registered in `_ALL_LOOPS`
(`backend/app/api/v1/system.py`, present after `4f9cb97` / subsequent union).

### Why it matters to a user

Market detail and the pods command center can show **descriptive** whale
pressure and venue gap — research telemetry, not auto-orders. Empty or stale
fields stay honest rather than inventing “smart money” narratives.

---

## V59 — Heartbeat position manager

### What shipped

There is **no** titled `merge(loop59): …` row in
`git log --oneline --merges -15`. Heartbeat still **landed on the integration
line** via migration re-chain + config union commits that appear in that log:

- `91239e3` — renumber heartbeat migration `051→052`, chain onto
  `051_venue_gaps` (single Alembic head)
- `09af5eb` — resolve `config.py` conflict: union of V58 whale/gap + V59
  heartbeat settings

Feature tickets (ancestors of the V57 merge-resolve):

| Ticket | SHA | Summary |
|--------|-----|---------|
| H1 | `8c4c293` | Decision engine: hold / tighten / exit / emergency rules |
| H2 | `75a3b54` | `heartbeat_manager` loop + decision_log migration |
| H3 | `303180c` | Emergency halt paths: staleness, daily-loss, kill switch |
| H4 | `15391a5` | `GET /api/v1/heartbeat/decisions` + ops runbook section |
| H5 | `ce099e9` | Tests + gate |

### Behavior

| Item | Detail |
|------|--------|
| Loop name | `heartbeat_manager` (in `_ALL_LOOPS`) |
| Default flag in code | `HEARTBEAT_MANAGER_ENABLED=false` (`backend/app/core/config.py`) |
| Cadence | `HEARTBEAT_MANAGER_INTERVAL_SEC` default 45s |
| Order path | CLOB exits only via RiskService → OrderIntent(`is_exit=True`) → OrderBookService |
| Audit | `GET /api/v1/heartbeat/decisions` (public read) |
| LLM | None in the heartbeat loop |

### Why it matters to a user

Paper positions can be managed by **code rules** (time stop, adverse move,
profit target, staleness, daily-loss halt) with a visible decision log —
still simulated funds only. JWT `*_logged` rows are recommendations until a
CLOB exit is `*_submitted` after risk approval.

---

## V57 — Multi-pod paper strategy engine

### What shipped

Merge-resolve:

- `40aeeec` — `merge-resolve(loop57): union loop registrations; re-chain 053_pods onto 052_heartbeat`

Tickets:

| Ticket | SHA | Summary |
|--------|-----|---------|
| P1 | `f1ab750` | Pod framework (`app/pods/`), migration `053_pods`, `PODS_ENABLED` default false |
| P2 | `79497b5` | Scoring engine (multi-factor stored-history score) |
| P3 | `48933a3` | Three concrete paper pods (crypto 5m momentum-fade, longshot-fade, sports value) |
| P4 | `3003a8c` | In-process `pod_runner` (~60s), heartbeat detail, public pods status API |
| P5 | `539117c` | Pod tests |

### Three paper pods (keys from live `GET /api/v1/pods` during V66 docs)

| Key | Display name (prod payload) |
|-----|------------------------------|
| `crypto_5m_momentum_fade` | Crypto 5M Momentum Fade |
| `longshot_fade` | Longshot Fade |
| `sports_value` | Sports Value |

### Flags & loops

| Flag / loop | Code default | Notes |
|-------------|--------------|-------|
| `PODS_ENABLED` | `false` in `config.py` | Runner no-ops when false (`pod_runner` skip reason) |
| `pod_runner` | registered in `_ALL_LOOPS` | 60s cadence when enabled |
| Order path | unchanged | RiskService → OrderIntent → OrderBookService only |

**Prod observation during V66 docs drafting (uptime host):**
`pod_runner` heartbeat `status=ok` with `scanned`/`scored` counts, and the
pods API returned `count: 3` with each pod `enabled: true` and
`paper_trading_only: true`. That is live API evidence, not a git SHA —
operator Railway env enables what code defaults leave off.

### Why it matters to a user

AlphaEdge can run **isolated paper strategies** 24/7 with their own scoring and
ledgers, without cash rails or bypassing risk. The `/pods` UI (V60) is how
humans watch that fleet.

---

## V60 — Pods command center UI (`/pods`)

### What shipped

Merge:

- `8ae25a4` — `merge(loop60): pods command center UI — fleet dashboard, decision terminal, context panels`

Tickets:

| Ticket | SHA | Summary |
|--------|-----|---------|
| U1 | `bc14e33` | Pods API contracts + view helpers (`lib/pods-api.ts`) |
| U2 | `3c9f9dc` | `/pods` fleet dashboard, status chips, sparklines, honest paper banner |
| U3 | `313ee4d` | Decision-log terminal — 5s poll, blink on new row, rule badge |
| U4 | `a9dc430` | Market context panel — whale gauge, venue gap, news tone, honest absent states |
| U5 | `ed9b223` | Frontend gate + STATE |

### User-visible surfaces

| Surface | Route / embed | Data |
|---------|---------------|------|
| Fleet dashboard | `/pods` | `GET /api/v1/pods` |
| Decision log terminal | on `/pods` | `GET /api/v1/heartbeat/decisions` |
| Market context panel | market detail | `GET /api/v1/markets/{slug}/context` |
| Nav | Header “More” → Pods | `HeaderMoreMenu` entry |

Honest states (no fabricated fleet numbers):

- 404 → “Pods API not yet deployed”
- unreachable → “Pods telemetry unavailable”
- empty list → “No pods registered yet”
- Banner: simulated funds — no execution

### Why it matters to a user

You can watch the paper pod fleet, recent heartbeat decisions, and per-market
context (whale / venue gap / news tone) without being told those panels place
trades.

---

## V54 — QA e2e honesty specs

### What shipped

Merge:

- `04162bc` — `merge(loop54): QA e2e specs — locked-forecast, bell/eval, resolved-count contract`

From loop STATE (goals/loop-v54-qa-sweep): chromium suite green for the new
specs (locked-forecast, loading-states for bell/eval, resolved-count
contract). Visreg remains a separate project (Loop V44 policy).

### Why it matters to a user

The honesty contracts Wave 9/10 product claims depend on (locked vs pre-lock
forecast, notification/eval loading shapes, resolved-count `source` /
cluster fields) have automated Playwright coverage — not just prose.

---

## V61 — Continuous sentiment desk (flag-gated)

### What shipped

Merge (present on the integration line; subject explicitly **flag-gated**):

- `ea2be72` — `merge(loop61): continuous sentiment desk — adaptive cadence, trend features, analyst lenses (flag-gated)`

Tickets:

| Ticket | SHA | Summary |
|--------|-----|---------|
| S1 | `7a9ac87` | Adaptive cadence for news/sentiment refresh |
| S2 | `45950a3` | Sentiment trend features |
| S3 | `aad10c9` | Analyst-debate pass (lenses) |
| S4 | `876ae23` | Wire into master context endpoint |
| S5 | `b28aa71` | Tests + full gate |

### Status note for operators

- Merge object **`ea2be72` exists** in this repository (verify:
  `git show --stat ea2be72`).
- Subject line says **flag-gated** — default product behavior stays off until
  operator flags enable the desk pieces.
- At V66 docs drafting, this docs branch tip may lag the integration branch
  that already contains `ea2be72`; treat deploy status as “confirm on target
  host,” not “always live on every worktree.”

### Why it matters to a user

Sentiment moves from occasional snapshot toward a **continuous desk**
(urgency-aware cadence, trend, multi-lens debate) that feeds master context
and pod inputs — still paper-only, still no raw order path from LLM text.

---

## Wave 10 index (quick SHAs)

| Loop | Headline | Primary SHA |
|---|---|---|
| V56 | Lock provenance | `ffedfa4` |
| — | Integrate 048 head | `133af64` |
| V58 | Whale flow + venue gaps + context | `4f9cb97` |
| V59 | Heartbeat land path | `09af5eb` / `91239e3` (+ tickets `8c4c293`…`ce099e9`) |
| V57 | Pods engine + `pod_runner` | `40aeeec` |
| V60 | `/pods` UI | `8ae25a4` |
| V54 | QA e2e specs | `04162bc` |
| V61 | Sentiment desk (flag-gated) | `ea2be72` |

Verify any row:

```text
git show --stat <sha>
```

Related ops: [docs/operations.md](../operations.md) §9 loops catalog.  
Related UX: [docs/user-guide.md](../user-guide.md) `/pods` section.
