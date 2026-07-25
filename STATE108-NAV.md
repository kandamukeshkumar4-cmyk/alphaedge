diff --git a/frontend/src/lib/feature-registry.ts b/frontend/src/lib/feature-registry.ts
index f3e9886..be996fe 100644
--- a/frontend/src/lib/feature-registry.ts
+++ b/frontend/src/lib/lib/feature-registry.ts
@@ -265,6 +265,12 @@ export const FEATURE_GROUPS: FeatureGroup[] = [
         href: "/home",
         blurb: "Your personal desk home.",
       },
+      {
+        id: "usage",
+        label: "Usage",
+        href: "/usage",
+        blurb: "Your paper-trading activity and API usage stats.",
+      },
     ],
   },
   {

typecheck and lint output:

cd frontend && npm run typecheck
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
'tsc' is not recognized as an internal or external command,
operable program or batch file.

cd frontend && npm run lint
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
'eslint' is not recognized as an internal or external command,
operable program or batch file.