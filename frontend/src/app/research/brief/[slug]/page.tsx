import { MARKETS } from "@/lib/mock-data";
import BriefBySlugClient from "./brief-client";

// Server wrapper so this route works under `output: "export"` (Azure SWA
// deploy): enumerate the known catalog slugs; the client component resolves
// the live brief at runtime. Unknown slugs 404 on the static host.
export function generateStaticParams() {
  return MARKETS.map((m) => ({ slug: m.slug }));
}

export default function BriefBySlugPage() {
  return <BriefBySlugClient />;
}
