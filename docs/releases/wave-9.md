# Wave 9 — Forecast maturity release notes

**Scope:** catalog→external bridge proven in prod, AI analyze honesty,
assistant depth, docs/Kalshi/locked-forecast transparency, lifecycle events,
cluster-gated model A/B, and a flag-off Nemotron signal.

**Rules for this page:** every claim cites a real git SHA from this repo.
No fabricated features, no secret values, paper-trading only.

Evidence basis:

```text
git log --oneline --merges -30
git log --oneline loop3-agent-memory -40
```

---

## V33 — Catalog bridge + source flip

### What shipped

Loop 33 closed the autolock **input starvation** problem: live catalog markets
were never written into `external_markets`, so the forecast auto-lock worker
saw zero candidates even while the catalog was full.

Merge:

- `64a74f7` — `merge(loop33): catalog->external_markets bridge + funnel observability + resolved-count honesty (B1-B3) — the pipeline finally has input`

That merge delivered:

1. **B2' bridge** — catalog → `external_markets` supply so autolock has rows.
2. **Funnel observability** — staged counts so “zero candidates” is diagnosable.
3. **Honest resolved-count source** — API discloses whether the count comes from
   real forecast scores or a paper-orders fallback.

### Why it matters to a user

Without this bridge, “model forecast near close” never accrues. After it
shipped, production could lock, resolve, and score pre-close forecasts.

### Notable follow-on (source flip)

Prod proof that the full chain works was recorded (not a product merge — a
measured runbook update):

- `f6bf87f` — `docs(loop40): THE FLIP — V33 proven end-to-end in prod (source=forecast_scores, 7 scored)`

Measured shape cited in that commit message:

```text
/api/v1/system/resolved-count
{"resolved_count": 7, "source": "forecast_scores", "forecast_scored_count": 7}
```

Chain confirmed in the commit narrative:

```text
live ingest → bridge → autolock (strictly pre-close) → venue resolve → score → resolved_count
```

Related accuracy-prep packaging:

- `13b490e` — `merge(loop40): accuracy-loop readiness runbook (docs)`

---

## V41 — AI Analyze must analyze

### What shipped

Keyless “Analyze …” no longer returns a capability menu. Root cause was
**both** a keyless deterministic fallback and an intent-router miss (no
analyze/deep-dive bucket).

Completion / review:

- `0d0f0e9` — `fix(loop41): REVIEW A2-A4 PASS — loop complete`

Implementation path:

- `2871a97` — A1 diagnosis (keyless + router miss)
- `5cd46d3` — A2 keyless analyze returns real deterministic analysis
- `b3322a8` — A3 mocked-LLM routing verification
- `6527c00` — A4 tests (keyless / mocked LLM / menu) + gate green

### Why it matters to a user

Tapping Analyze on a market now yields a real analysis path (deterministic
when no LLM key; LLM when present). Unrecognized intents still show the menu —
analysis does not.

### Notable fixes

- Menu only for unrecognized intents; analyze seed paths set menu false.
- No order placement from assistant analysis (analysis-only; paper path
  unchanged).

---

## V42 — Assistant intelligence depth

### What shipped

Merge:

- `2a50264` — `merge(loop42): assistant intelligence depth M1-M4 — model probability, bear-case, exposure`

Tickets:

- M1 on-demand model probability — `83c5191`
- M2 bear-case depth — `b97cf9f`
- M3 authenticated exposure depth — `5145498`
- M4 tests + verifier notes — `a53b326`

Adjacent keyless polish (same assistant surface family):

- `aa537f8` — `fix(loop42): humanize+dedupe keyless analyze signal drivers`

### Why it matters to a user

The assistant can answer deeper questions: what the model says now, what a
bear case looks like, and (when authenticated) exposure context — without
pretending to submit trades.

---

## V45 — Docs sync to the live surface

### What shipped

Merge:

- `298bf3f` — `merge(loop45): docs sync W1-W3 — api/user-guide/operations aligned to live surface`

Work commits:

- `53ed5f7` — W1 `docs/api.md` vs OpenAPI snapshot (social, notifications,
  admin, eval/drift, models, resolved-count source)
- `78563ea` — W2 user-guide (bell, profiles/following, `/eval`, honest
  resolved-count source)
- `0e6fb70` — W3 operations runbook (`_ALL_LOOPS`, bridge/digest/retention,
  autolock funnel, visreg, CI)

### Why it matters to a user

Product and ops docs describe the same APIs and loops the app actually runs —
including social, notifications, and honest score-source disclosure.

---

## V46 — Kalshi open-events widening

### What shipped

Review close:

- `9b7af40` — `fix(loop46): REVIEW K1-K3 PASS — loop complete`

Path:

- `bea27a5` — K1 audit: `kalshi_open_events` `skipped=200` was **100% board-join miss**
- `2fa7c7d` — K2/K3 event-market board-join fallback + raised caps + tests

### Why it matters to a user

Kalshi discovery was importing nothing useful when every open event failed to
join the truncated global markets board. Widening restores a real Kalshi
surface for paper markets instead of a permanent skip=200.

### Notable fixes

- Root cause was events-first discovery + empty intersection with a multigame-
  dominated `/markets` cursor — not a volume floor or category denylist
  (per K1 audit in `bea27a5` / loop STATE).

---

## V47 / V48 — Locked-forecast transparency

### What shipped (backend unlock first)

- `c64b04f` — `merge(loop48): unlock locked-forecast endpoint for F1/F2`
- `bfc926a` — `fix(loop48): U1 / U2`

Endpoint: `GET /api/v1/markets/{slug}/locked-forecast` with an honest locked
vs pre-lock shape (no invented percentages).

### What shipped (UI + disclosure)

- `102ff42` — F3 resolved-count disclosure on track-record; F1/F2 initially
  blocked on backend
- `e494764` — F1–F2 after unlock
- `59bee3d` — `feat(loop47): REVIEW F1-F2 PASS — loop complete`

User-visible panel behavior (from completed loop STATE, tied to those commits):

- Locked: model lock %, relative lock time, vs market now + delta, provisional flag
- Pre-lock: “Model forecast locks near close” — never a fake %
- Track-record surfaces `forecast_scored_count` + `source`

### Why it matters to a user

You can see **whether** a model forecast is locked and **how it compares to
the market**, and you can see whether resolved-count is real forecast scores
or a fallback — paper-trading honesty without cash claims.

---

## V49 — Forecast lifecycle events

### What shipped

Merge:

- `3e8f3a3` — `merge(loop49): forecast lifecycle events E1-E4 — WS channel, watcher notify, bridge heartbeat parity`

Tickets:

- `c62b942` — E1 WebSocket `forecasts` channel
- `3655f70` — E2 watcher notifications on forecast lock/resolve
- `8b82d41` — E3 tests for forecasts WS + watcher notify
- `6c7b9a6` — E4 bridge heartbeat detail parity
- `4d678e0` — STATE E1–E4 DONE with gate proof

### Why it matters to a user

Lock and resolve are pushable events. Watchers can be notified; ops heartbeats
can show bridge detail parity instead of silent empty detail after restarts.

---

## V51 — Cluster-gated A/B retarget + LightGBM image fix

### What shipped

Merge:

- `9e686ab` — `merge(loop51): A/B harness retarget to forecast_scores — cluster gate (>=100), cluster bootstrap, MDE reporting`

Implementation:

- `a32a88c` — `feat(loop51): retarget forecast score ab harness`
- `ab316f4` — record A/B verification state

### Behavior (from merge + implementation)

- Comparison population is **`forecast_scores` → forecast_logs → external_markets**
  — paper-order / legacy snapshot rows cannot enter the comparison.
- **`ab_ready`** is gated on a **correlation-cluster threshold of ≥100** (not a
  raw row vanity count alone), with concentration / MDE reporting retained.
- Public `GET /api/v1/system/model-ab` is **cache-only**; training refreshes are
  controlled job runs, not implicit on every GET.
- **LightGBM fix:** `backend/Dockerfile` installs the lock-pinned `ml-extra`
  extra (`uv sync --no-dev --extra ml-extra`) so the A/B harness cannot silently
  fall back to XGBoost when LightGBM should be the real arm
  (see Dockerfile hunk in `a32a88c` / `9e686ab`).

### Why it matters to a user

“Is model A better than model B?” only becomes answerable on a population of
**real scored forecasts**, with a cluster gate that resists tiny correlated
samples — and with the correct ML library actually present in the deploy image.

### Honesty constraints retained

- Historical `ML_MODEL_TYPE` constancy is not invented: harness can refuse with
  `model_type_history_unverified` until operator evidence is set (documented in
  V51 STATE on the merge).
- `PAPER_TRADING_ONLY` remains required.

---

## V52 — Nemotron reasoning signal (flag-off)

### What shipped

Merge:

- `8e71c96` — `merge(loop52): Nemotron-3 NIM reasoning signal + Ralph AutoLab lab (flag-off)`

Tickets:

- `f6f31b9` — N1 `nemotron_signal` NIM chat + cache + circuit breaker
- `ab1c104` — N2 wire `nemotron_node` into prediction graph
- `a4cf22c` — N3 `ralph_signal_lab` offline AutoLab runner
- `4c810d0` — N4 tests + gate

### Why it matters to a user

A stronger optional reasoning signal and an offline AutoLab lab are **in the
tree**, but the feature ships **flag-off**. Default product behavior does not
change until an operator enables the flag. No cash trading path is introduced.

---

## Wave 9 index (quick SHAs)

| Loop | Headline | Primary SHA |
|---|---|---|
| V33 | Bridge + funnel + honest resolved-count | `64a74f7` |
| V33 flip | Prod source=`forecast_scores` | `f6bf87f` |
| V41 | Analyze fix | `0d0f0e9` |
| V42 | Assistant depth M1–M4 | `2a50264` |
| V45 | Docs sync | `298bf3f` |
| V46 | Kalshi widening | `9b7af40` |
| V48 | Locked-forecast API | `c64b04f` |
| V47 | Locked-forecast UI + disclosure | `59bee3d` |
| V49 | Forecast lifecycle events | `3e8f3a3` |
| V51 | Cluster-gated A/B + LightGBM image | `9e686ab` |
| V52 | Nemotron + Ralph lab (flag-off) | `8e71c96` |

Verify any row:

```text
git show --stat <sha>
```
