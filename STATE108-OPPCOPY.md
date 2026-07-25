# STATE108-OPPCOPY — honest copy for `no_validated_edge` empty state

Frontend copy task: the backend (loop107, `backend/app/api/v1/opportunities.py`)
added `empty_reason="no_validated_edge"` (predictions exist, but no factor
currently beats the closing line out-of-sample). The frontend opportunity
scanner did not handle that reason yet — it fell through to the default branch.

Changes:

1. `frontend/src/lib/opportunities-api.ts` — added `"no_validated_edge"` to the
   `empty_reason` union on `OpportunitiesResponse` (required for the new switch
   case to typecheck).
2. `frontend/src/app/opportunities/page.tsx` — added a `case "no_validated_edge"`
   to the `raw.empty_reason` switch, in the exact style of the
   `no_model_predictions` case. No funnel counts are rendered by any case in
   this component, so no funnel UI was added.

## Final implementation

### git diff (the two source files, pre-staging)

```diff
diff --git a/frontend/src/app/opportunities/page.tsx b/frontend/src/app/opportunities/page.tsx
index e4ccd5f..d7042c0 100644
--- a/frontend/src/app/opportunities/page.tsx
+++ b/frontend/src/app/opportunities/page.tsx
@@ -68,6 +68,8 @@ export default function OpportunitiesPage() {
     switch (raw.empty_reason) {
       case "no_model_predictions":
         return "No open market has a stored model probability yet. Edges are ranked only from real PredictionLog rows — never fabricated. The model-vs-market scanner stays empty until predictions are written for live markets.";
+      case "no_validated_edge":
+        return "No validated edges right now. Model predictions exist, but none currently beat the closing line out-of-sample. This board only lists edges that survive validation — an empty list is the model being honest, not the app being broken.";
       case "no_open_candidates":
         return "No open markets are in the current candidate set (top volume slice). Resolved or locked markets are not ranked as live edges.";
       case "no_market_prices":
diff --git a/frontend/src/lib/opportunities-api.ts b/frontend/src/lib/opportunities-api.ts
index 1bfe8cc..caccfc1 100644
--- a/frontend/src/lib/opportunities-api.ts
+++ b/frontend/src/lib/opportunities-api.ts
@@ -68,6 +68,7 @@ export type OpportunitiesResponse = {
     | "filtered_by_min_liquidity"
     | "filtered_by_direction"
     | "no_rankable_edges"
+    | "no_validated_edge"
     | null;
   paper_trading_only: boolean;
   signal_only: boolean;
```

### Verification (foreground; `cd frontend && npm ci` first — node_modules was absent)

`cd frontend && npm ci` → `added 649 packages, and audited 650 packages in 1m`

`cd frontend && npm run typecheck` — exit code 0. Verbatim output (the last
lines of the command; tsc prints nothing on success):

```text

> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

`cd frontend && npm run lint` — exit code 0. Verbatim output (the last lines of
the command; eslint prints nothing on a clean run with `--max-warnings=0`):

```text

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```
