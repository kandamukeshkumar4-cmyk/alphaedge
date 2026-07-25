# STATE109-UI — Mirror new scanner step types in UI

Task: backend added two scanner step types (`CROSS_VENUE_DIVERGENCE`,
`CLOSING_SOON`); the frontend enumerated the old five in 8 sites and would
render the new types as unknown. Added the two new types at every site,
following each site's existing pattern.

## Sites (all 8 verified present — none absent)

- `frontend/src/lib/scanners-api.ts`
  - `ScannerStepType` union (~L50)
  - `SCANNER_STEP_TYPES` enum array (~L239)
  - `stepLabel` display map (~L481) — labels verbatim from backend truth
  - `mockRead` switch (~L597) — new types return `{}` (no mock read shape defined)
  - `candidateHasRead` (~L528) — forced type-level consequence of the union
    widening (see note below), same named file
- `frontend/src/components/scanners/ScannerCanvas.tsx`
  - `stepBlurb` switch (~L127) — one-liners verbatim from backend truth
- `frontend/src/components/scanners/ScannerCard.tsx`
  - `STEP_ABBREV` Record (~L28) — `"venue"`, `"closing"`
- `frontend/src/components/scanners/ScannerDetailShell.tsx`
  - `readPill` switch (~L92) — new types return `null` (no candidate read shape yet)
  - `narrationForStep` switch (~L763) — "Comparing venue prices" / "Scanning closing markets"

## Note — candidateHasRead (deviation disclosure)

Widening the `ScannerStepType` union made `cand.reads[type]` a TS7053 error:
`ScannerReads` has no keys for the new types. Fixed with a typed cast
(`Partial<Record<ScannerStepType, unknown>>`) in the same named file —
runtime semantics unchanged (new types resolve to `undefined` → absent).
Did not invent read shapes for the new types (backend contract does not
specify them).

## Verification (cd frontend; npm ci ran first — node_modules was absent, exit 0)

### `npm run typecheck`

First run failed (verbatim):

```
src/lib/scanners-api.ts(528,10): error TS7053: Element implicitly has an 'any' type because expression of type 'ScannerStepType' can't be used to index type 'ScannerReads'.
  Property 'CROSS_VENUE_DIVERGENCE' does not exist on type 'ScannerReads'.
```

Fixed (cast above), re-run passed — literal verbatim last lines:

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

(exit code 0, no diagnostics)

### `npm run lint`

Literal verbatim last lines:

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

(exit code 0, no output)

## git diff

```
 frontend/src/components/scanners/ScannerCanvas.tsx    |  4 ++++
 frontend/src/components/scanners/ScannerCard.tsx      |  2 ++
 .../src/components/scanners/ScannerDetailShell.tsx    |  8 ++++++++
 frontend/src/lib/scanners-api.ts                      | 19 +++++++++++++++++--
 4 files changed, 31 insertions(+), 2 deletions(-)
```

```diff
diff --git a/frontend/src/components/scanners/ScannerCanvas.tsx b/frontend/src/components/scanners/ScannerCanvas.tsx
index 9074606..3928ae7 100644
--- a/frontend/src/components/scanners/ScannerCanvas.tsx
+++ b/frontend/src/components/scanners/ScannerCanvas.tsx
@@ -126,6 +126,10 @@ function stepBlurb(step: ScannerStep): string {
       return "Model prob vs market mid (paper)";
     case "DIRECTION_ALIGNMENT":
       return "Keep only agreeing directions";
+    case "CROSS_VENUE_DIVERGENCE":
+      return "Price gap between Polymarket and Kalshi for the same event.";
+    case "CLOSING_SOON":
+      return "Markets locking within the next N hours.";
   }
 }
 
diff --git a/frontend/src/components/scanners/ScannerCard.tsx b/frontend/src/components/scanners/ScannerCard.tsx
index efd2733..df2d599 100644
--- a/frontend/src/components/scanners/ScannerCard.tsx
+++ b/frontend/src/components/scanners/ScannerCard.tsx
@@ -26,6 +26,8 @@ const STEP_ABBREV: Record<ScannerStepType, string> = {
   NEWS_SENTIMENT: "news",
   MODEL_EDGE: "model",
   DIRECTION_ALIGNMENT: "align",
+  CROSS_VENUE_DIVERGENCE: "venue",
+  CLOSING_SOON: "closing",
 };
 
 function staggerClass(index: number): string {
diff --git a/frontend/src/components/scanners/ScannerDetailShell.tsx b/frontend/src/components/scanners/ScannerDetailShell.tsx
index dbe0832..3bd2bc4 100644
--- a/frontend/src/components/scanners/ScannerDetailShell.tsx
+++ b/frontend/src/components/scanners/ScannerDetailShell.tsx
@@ -91,6 +91,10 @@ function readPill(
     }
     case "DIRECTION_ALIGNMENT":
       return null; // alignment renders as the checkmark column, not a pill
+    case "CROSS_VENUE_DIVERGENCE":
+      return null; // loop109 types carry no candidate read shape yet — no pill
+    case "CLOSING_SOON":
+      return null;
   }
 }
 
@@ -762,6 +766,10 @@ function narrationForStep(step: ScannerStep): string {
       return "Computing model edge";
     case "DIRECTION_ALIGNMENT":
       return "Scoring alignment";
+    case "CROSS_VENUE_DIVERGENCE":
+      return "Comparing venue prices";
+    case "CLOSING_SOON":
+      return "Scanning closing markets";
   }
 }
 
diff --git a/frontend/src/lib/scanners-api.ts b/frontend/src/lib/scanners-api.ts
index 4633045..1ef6834 100644
--- a/frontend/src/lib/scanners-api.ts
+++ b/frontend/src/lib/scanners-api.ts
@@ -47,7 +47,9 @@ export type ScannerStepType =
   | "PRICE_TREND"
   | "NEWS_SENTIMENT"
   | "MODEL_EDGE"
-  | "DIRECTION_ALIGNMENT";
+  | "DIRECTION_ALIGNMENT"
+  | "CROSS_VENUE_DIVERGENCE"
+  | "CLOSING_SOON";
 
 export type ScannerStep = {
   type: ScannerStepType;
@@ -237,6 +239,8 @@ export const SCANNER_STEP_TYPES: readonly ScannerStepType[] = [
   "NEWS_SENTIMENT",
   "MODEL_EDGE",
   "DIRECTION_ALIGNMENT",
+  "CROSS_VENUE_DIVERGENCE",
+  "CLOSING_SOON",
 ];
 
 function normalizeStep(raw: unknown): ScannerStep | null {
@@ -480,6 +484,10 @@ export function stepLabel(step: ScannerStep): string {
       return "Model vs market";
     case "DIRECTION_ALIGNMENT":
       return "Direction alignment";
+    case "CROSS_VENUE_DIVERGENCE":
+      return "Cross-Venue Divergence";
+    case "CLOSING_SOON":
+      return "Closing Soon";
   }
 }
 
@@ -517,7 +525,9 @@ export function relativeTimeLabel(iso: string, nowMs: number = Date.now()): stri
 
 /** Does the candidate's reads map carry a read for this step type? */
 export function candidateHasRead(cand: ScannerCandidate, type: ScannerStepType): boolean {
-  return cand.reads[type] !== undefined;
+  // The loop109 step types carry no read shape on ScannerReads yet — widen
+  // the index so they resolve to `undefined` (absent) instead of a type error.
+  return (cand.reads as Partial<Record<ScannerStepType, unknown>>)[type] !== undefined;
 }
 
 // ---------------------------------------------------------------------------
@@ -596,6 +606,11 @@ function mockRead(step: ScannerStep, marketIndex: number): ScannerReads {
     }
     case "DIRECTION_ALIGNMENT":
       return { DIRECTION_ALIGNMENT: { aligned: marketIndex % 2 === 0 } };
+    case "CROSS_VENUE_DIVERGENCE":
+      // loop109 step types carry no mock read shape yet — empty reads.
+      return {};
+    case "CLOSING_SOON":
+      return {};
   }
 }
```
