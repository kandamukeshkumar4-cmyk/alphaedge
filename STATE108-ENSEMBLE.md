## Git Diff

```diff
diff --git a/frontend/src/app/eval/page.tsx b/frontend/src/app/eval/page.tsx
index 372fdaf..5a28629 100644
--- a/frontend/src/app/eval/page.tsx
+++ b/frontend/src/app/eval/page.tsx
@@ -50,8 +50,9 @@ function StatCard({ label, value }: { label: string; value: React.ReactNode }) {
 export default function EvalDashboard() {
   const [aggregates, setAggregates] = useState<EvalAggregates | null>(null);
   const [autolab, setAutolab] = useState<AutoLabMeasurement | null>(null);
+  const [unavailable, setUnavailable] = useState(false);
 
-  useEffect(() => {
+useEffect(() => {
     if (!API) return;
 
     fetch(`${API}/api/v1/eval/aggregates`)
@@ -72,9 +73,12 @@ export default function EvalDashboard() {
       notes: "Ensemble comparison has not been run yet.",
     };
     fetch(`${API}/api/v1/ensemble/autolab`)
-      .then((r) => (r.ok ? r.json() : null))
-      .then((data) => setAutolab(data ? (data as AutoLabMeasurement) : notRun))
-      .catch(() => setAutolab(notRun));
+      .then((r) => {
+        if (!r.ok) throw new Error(`${r.status}`);
+        return r.json();
+      })
+      .then((data) => setAutolab(data as AutoLabMeasurement))
+      .catch(() => setUnavailable(true));
   }, []);
 
   const ensembleBetter =
@@ -119,9 +123,19 @@ export default function EvalDashboard() {
           . Flag only turns ON when ensemble Brier is measurably lower than baseline.
         </p>
 
-        {autolab === null ? (
+        {autolab === null && !unavailable ? (
           <p className="mt-4 text-sm text-muted-2">Loading…</p>
-        ) : autolab.outcome === "not_run" || autolab.outcome === "insufficient_data" ? (
+        ) : unavailable ? (
+          <div
+            data-testid="ensemble-unavailable"
+            className="mt-4 rounded-2xl border border-muted/30 bg-muted/10 p-4"
+          >
+            <p className="text-sm font-medium text-text">
+              Ensemble AutoLab: not yet measured. This section will populate when
+              the ensemble evaluation pipeline ships.
+            </p>
+          </div>
+        ) : autolab && (autolab.outcome === "not_run" || autolab.outcome === "insufficient_data") ? (
           /* Honest "not yet measured" state — never fabricate bars */
           <div
             data-testid="ensemble-not-measured"
@@ -139,12 +153,12 @@ export default function EvalDashboard() {
             </p>
           </div>
         ) : (
-          /* Real numbers — outcome === "measured" */
+          /* Real numbers — outcome === "measured" (guaranteed by elimination) */
           <div data-testid="ensemble-measured" className="mt-4 space-y-4">
             <dl className="grid grid-cols-2 gap-3">
               <StatCard
                 label="Single-model Brier"
-                value={autolab.baseline_brier?.toFixed(4) ?? "—"}
+                value={autolab!.baseline_brier?.toFixed(4) ?? "—"}
               />
               <div className="rounded-2xl border border-border bg-surface p-4">
                 <dt className="text-xs font-bold uppercase tracking-[0.06em] text-muted">
@@ -156,20 +170,20 @@ export default function EvalDashboard() {
                     ensembleBetter ? "text-up" : "text-danger",
                   )}
                 >
-                  {autolab.ensemble_brier?.toFixed(4) ?? "—"}
+                  {autolab!.ensemble_brier?.toFixed(4) ?? "—"}
                 </dd>
               </div>
-              <StatCard label="Resolved markets (n)" value={autolab.n_samples} />
+              <StatCard label="Resolved markets (n)" value={autolab!.n_samples} />
               <StatCard
                 label="Improvement"
                 value={
-                  autolab.ensemble_brier !== null && autolab.baseline_brier !== null
-                    ? `${((autolab.baseline_brier - autolab.ensemble_brier) * 100).toFixed(2)}pp`
+                  autolab!.ensemble_brier !== null && autolab!.baseline_brier !== null
+                    ? `${((autolab!.baseline_brier - autolab!.ensemble_brier) * 100).toFixed(2)}pp`
                     : "—"
                 }
               />
             </dl>
-            <p className="text-xs text-muted-2">{autolab.notes}</p>
+            <p className="text-xs text-muted-2">{autolab!.notes}</p>
           </div>
         )}
       </section>
```

## Typecheck Output (last lines)

```
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

(no errors)

## Lint Output (last lines)

```
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

(no errors, no warnings)