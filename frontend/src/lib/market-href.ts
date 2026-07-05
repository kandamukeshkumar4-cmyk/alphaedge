import { MARKETS } from "./mock-data";

// Static export only pre-builds /markets/[slug] for the seed catalog; live
// mirrored markets (pm-*, ks-*) resolve through the query-param route instead.
const STATIC_SLUGS = new Set(MARKETS.map((m) => m.slug));

export function marketHref(slug: string): string {
  if (STATIC_SLUGS.has(slug)) return `/markets/${slug}`;
  return `/markets/view?slug=${encodeURIComponent(slug)}`;
}
