import type { NextConfig } from "next";

// `output: "export"` (static export for the Azure SWA deploy) requires every
// dynamic route to be enumerated in generateStaticParams — impossible for the
// live market catalog, and it 500s every /markets/[slug] page in normal dev/
// server mode. So static export is OPT-IN: only `npm run build:static` (the
// deploy path; npm exposes the script name as npm_lifecycle_event) or an
// explicit STATIC_EXPORT=1 enables it; dev and normal builds serve dynamically.
const staticExport =
  process.env.STATIC_EXPORT === "1" ||
  process.env.npm_lifecycle_event === "build:static";

// Browser → Vercel → Railway (always-on backend; migrated off the free HF
// Space which had no SLA + rebuild downtime). Same-origin rewrites keep
// health/markets/ATLAS readable in the browser. NEXT_PUBLIC_API_URL overrides.
const PROD_API =
  (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "") ||
  "https://alphaedge-api-production-b9db.up.railway.app";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(staticExport ? { output: "export" as const } : {}),
  ...(!staticExport
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${PROD_API}/api/:path*`,
            },
            {
              source: "/health",
              destination: `${PROD_API}/health`,
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
