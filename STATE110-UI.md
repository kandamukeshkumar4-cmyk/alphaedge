# STATE110-UI — render after_signal_gate in opportunities funnel

Task: in `frontend/src/app/opportunities/page.tsx` (and ONLY there), render ALL
backend funnel stages — including the new `after_signal_gate` stage — in
pipeline order, labeled "Passed validation gate".

## Findings

- Backend funnel shape (verified in `backend/app/api/v1/opportunities.py`,
  lines 234–243), pipeline order:
  `candidates_scanned, candidates_open, with_model_p, with_market_p,
  after_signal_gate, after_min_liquidity, after_direction, returned`.
- `frontend/src/app/opportunities/page.tsx` did NOT render any funnel counts
  before this change — the empty state was copy-only (`emptyStateBody()`).
- The lib type (`frontend/src/lib/opportunities-api.ts`,
  `OpportunitiesResponse["funnel"]`) predates `after_signal_gate`. Since the
  task is scoped to the page file only, the page widens the type locally
  (`type FunnelCounts = NonNullable<OpportunitiesResponse["funnel"]> & {
  after_signal_gate: number }`).

## Change

Added a compact one-line stage list under the empty-state copy (plain DOM
text), e.g.
`97 scanned → 97 open → 50 with predictions → 48 with market price → 0 passed
validation gate → 0 past min liquidity → 0 past direction filter → 0 returned`.
Renders only when the backend reported funnel counts (`raw?.funnel`); null-safe
against older backends and the unreachable-scanner case. Nothing else changed.

## git diff

```diff
diff --git a/frontend/src/app/opportunities/page.tsx b/frontend/src/app/opportunities/page.tsx
index d7042c0..6f9ae69 100644
--- a/frontend/src/app/opportunities/page.tsx
+++ b/frontend/src/app/opportunities/page.tsx
@@ -29,6 +29,25 @@ const LIQUIDITY_STEPS: { value: number; label: string }[] = [
   { value: 100_000, label: "100K+" },
 ];
 
+// Loop110: the backend funnel now reports an ``after_signal_gate`` stage (the
+// Loop107 CLV gate, between with_market_p and after_min_liquidity) that the
+// lib type predates — widen it locally so every pipeline stage renders, in
+// pipeline order, so an honest empty stays explainable stage by stage.
+type FunnelCounts = NonNullable<OpportunitiesResponse["funnel"]> & {
+  after_signal_gate: number;
+};
+
+const FUNNEL_STAGES: { key: keyof FunnelCounts; label: string }[] = [
+  { key: "candidates_scanned", label: "scanned" },
+  { key: "candidates_open", label: "open" },
+  { key: "with_model_p", label: "with predictions" },
+  { key: "with_market_p", label: "with market price" },
+  { key: "after_signal_gate", label: "passed validation gate" },
+  { key: "after_min_liquidity", label: "past min liquidity" },
+  { key: "after_direction", label: "past direction filter" },
+  { key: "returned", label: "returned" },
+];
+
 const intFmt = (n: number) => String(Math.round(n));
 const ptsFmt = (n: number) => `${(n * 100).toFixed(1)} pts`;
 
@@ -58,6 +77,14 @@ export default function OpportunitiesPage() {
 
   const topEdge = view.rows[0]?.edge ?? 0;
 
+  // Loop110: compact one-line pipeline funnel for the empty state — plain text
+  // like "97 open → 50 with predictions → 0 passed validation gate", null when
+  // the backend didn't report funnel counts.
+  const funnel = (raw?.funnel ?? null) as FunnelCounts | null;
+  const funnelLine = funnel
+    ? FUNNEL_STAGES.map((s) => `${funnel[s.key]} ${s.label}`).join(" → ")
+    : null;
+
   // DIAGNOSIS106-OPPS: the honest empty explains ITSELF — branch on the
   // backend's machine-stable empty_reason, keeping the unreachable and
   // client-filter fallbacks. Copy never implies fabricated edges.
@@ -154,6 +181,9 @@ export default function OpportunitiesPage() {
         <div className="rounded-2xl border border-dashed border-border bg-surface px-4 py-8 text-sm text-muted">
           <p className="font-semibold text-text">No opportunities meet the filter right now.</p>
           <p className="mt-1">{emptyStateBody()}</p>
+          {funnelLine !== null && (
+            <p className="mt-2 text-xs text-muted-2">{funnelLine}</p>
+          )}
         </div>
       ) : (
         <div className="grid gap-3 md:grid-cols-2">
```

## Verification (LITERAL verbatim outputs)

`node_modules` was absent — `npm ci` run in `frontend/` first (completed).

### `cd frontend && npm run typecheck` — exit 0

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

### `cd frontend && npm run lint` — exit 0

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

AutoLab: not applicable (no iterative measure — one-shot UI render fix verified
by typecheck + lint).
