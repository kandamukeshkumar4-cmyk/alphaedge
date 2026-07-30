# Explorer notes — admin-eval.spec.ts test timeout/locator not found (line ~67)

## Summary
All test selectors exist in current code. Test was hardened in loop28 (commit 165ee66) for React hydration; recent changes (loop117) only modified label text. Failure likely due to async API data loading timeouts rather than selector drift.

## Files affected
- **Test:** `frontend/e2e/admin-eval.spec.ts` line 67 — test entry point; lines 38–180 define selectors
- **Admin layout:** `frontend/src/app/admin/layout.tsx` lines 28–71 — key input form (conditionally shown based on needsPrompt state)
- **Stats card:** `frontend/src/components/admin/AdminStatsCard.tsx` lines 34–71 — heading always visible; stats table only if data loaded
- **Markets table:** `frontend/src/components/admin/AdminMarketsTable.tsx` lines 94–187 — id="markets" section; heading "Markets" at line 96
- **Eval page:** `frontend/src/app/eval/page.tsx` lines 90–203 — PageHeader renders "Proof dashboard" as h1
- **Drift panel:** `frontend/src/components/DriftSeriesPanel.tsx` lines 28–108 — data-testid="drift-series-panel"; heading at line 32

## All selectors verified present
✓ Line 38–39: "Admin API Key" heading — layout.tsx:30 (h1 element)
✓ Line 41: "#admin-api-key" input — layout.tsx:40
✓ Line 54: "Save Key" button — layout.tsx:52–53
✓ Line 58: "Change API key" button — layout.tsx:68 (shown after needsPrompt=false)
✓ Line 101: "System stats" heading — AdminStatsCard.tsx:36 (h2 element)
✓ Line 103–107: "Users" / "Open markets" / "Trades · 24h" text labels — AdminStatsCard.tsx:53–55 (Stat components)
✓ Line 109: "#stats" section element — AdminStatsCard.tsx:34
✓ Line 118: "#markets" section element — AdminMarketsTable.tsx:94
✓ Line 120: "Markets" heading in #markets section — AdminMarketsTable.tsx:96 (h2 element)
✓ Line 147: "Proof dashboard" title — PageHeader component renders as h1 (eval/page.tsx:93)
✓ Line 150: "drift-series-panel" testid — DriftSeriesPanel.tsx:28
✓ Line 153: "Calibration drift history" heading — DriftSeriesPanel.tsx:32 (h2 element)
✓ Line 157–160: Regex text match — all four patterns verified:
  - "No drift snapshots yet" — DriftSeriesPanel.tsx:52
  - "Drift data is unavailable right now" — DriftSeriesPanel.tsx:50
  - "Latest Brier" — DriftSeriesPanel.tsx:68 (MetricTile label)
  - "Latest snapshot is..." — DriftSeriesPanel.tsx:62–64 (status message with degraded/guardrail check)
✓ Line 163: "ensemble-autolab-section" testid — eval/page.tsx:119 (section)
✓ Line 166: "ensemble-not-measured" testid — eval/page.tsx:146 (div)
✓ Line 167: "ensemble-measured" testid — eval/page.tsx:162 (div)

## Root cause analysis
**Code structure is correct; issue is async data loading timeout.**

1. **Admin key entry flow** (test lines 32–60):
   - Form shown when `needsPrompt === true` (layout.tsx:28–56)
   - Submit handler sets `setApiKey()` and `setNeedsPrompt(false)` (layout.tsx:18–19)
   - "Change API key" button appears when `needsPrompt === false` (layout.tsx:58–70)
   - ✓ Already hardened for React hydration (loop28 commit 165ee66): uses pressSequentially + waitForFunction to verify input.value before clicking Save

2. **Stats loading** (test lines 99–115):
   - Heading renders immediately when AdminStatsCard mounts (always visible)
   - Stats table only renders if `stats !== null` (AdminStatsCard.tsx:51–64)
   - Data fetched via `fetchAdminStats(apiKey)` on mount (useEffect line 29–31)
   - **Failure point:** If `/api/v1/admin/stats` does not respond within timeout, stats table never appears

3. **Markets loading** (test lines 117–133):
   - Table section renders immediately (AdminMarketsTable.tsx:94)
   - Row iteration only if `displayed.length > 0` (line 146–173)
   - Data fetched via `fetchAdminMarkets(apiKey)` on mount (useEffect line 54–56)
   - **Failure point:** If `/api/v1/admin/markets?limit=200` does not respond, no rows appear; test fails finding market row with CANONICAL_SLUG

4. **Drift panel loading** (test lines 150–160):
   - Section renders immediately; heading always visible (DriftSeriesPanel.tsx:28–32)
   - Data fetched via `fetchDriftSeries()` on mount (useEffect line 17–19); fails gracefully if unavailable (line 49–54)
   - **Failure point:** Timeout waiting for data or text to match regex

5. **Recent label-only changes** (loop117 commit 857112a):
   - Changed eval/page.tsx:100 "Mean Brier (7d)" → "Mean Brier (7d) — market-baseline"
   - Changed eval/page.tsx:120 ensemble heading to add "— market-baseline"
   - Changed eval/page.tsx:165 "Single-model Brier" → "Single-model Brier (market-baseline)"
   - **No structural/selector changes**

## Most likely failure point (in order)
1. **Line 100–115:** Timeout waiting for stats section after admin key saved
   - Check: Is `/api/v1/admin/stats` returning data in local-stack?
   - Check: Is NEXT_PUBLIC_API_URL set correctly?
2. **Line 123–133:** Timeout waiting for markets table rows or canonical market row
   - Check: Is `/api/v1/admin/markets` endpoint responding?
   - Check: Is CANONICAL_SLUG ("nba-2025-01-15-lal-bos") present in market list?
3. **Line 150–160:** Timeout waiting for drift panel text
   - Check: Is `/api/v1/eval/drift` responding (or 404 gracefully)?
   - Check: Is `/api/v1/ensemble/autolab` responding (or 404 gracefully)?

## Do not touch
- `frontend/src/app/admin/page.tsx` — component structure unchanged since creation
- `frontend/e2e/helpers/session.ts` — skipOnboarding + dismissOnboardingIfPresent already correct (loop72 C2 hygiene update)
- `frontend/src/components/ui/kit.tsx` — PageHeader structure verified correct

## Risks
No guardrails apply (no PAPER_TRADING_ONLY, no order path, no CLV gate involved in test).
Test is read-only fixture; no code changes required if root cause is API unavailability.

## Next step recommendation
Root issue is **timeout, not selector drift**. Run failing test with network tracing / verbose logs to identify exact which selector + timeout fails first. Verify local-stack API responses within test timeouts. If APIs are responding correctly but test still times out, issue may be React state/hydration (already mitigated but not fully eliminated by loop28 fix) — in that case, add waitForFunction assertions after setApiKey state changes.
