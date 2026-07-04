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

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(staticExport ? { output: "export" as const } : {}),
};

export default nextConfig;
