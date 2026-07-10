import { MARKETS } from "./mock-data";

// Static export only pre-builds /markets/[slug] for the seed catalog; live
// mirrored markets (pm-*, ks-*) resolve through the query-param routes instead.
const STATIC_SLUGS = new Set(MARKETS.map((m) => m.slug));

export function marketHref(slug: string, params?: Record<string, string>): string {
  if (STATIC_SLUGS.has(slug)) {
    const query = params ? new URLSearchParams(params).toString() : "";
    return query ? `/markets/${slug}?${query}` : `/markets/${slug}`;
  }
  const query = new URLSearchParams({ slug, ...(params ?? {}) });
  return `/markets/view?${query.toString()}`;
}

// D03: deep-link to the market detail Intelligence panel (desk aggregate).
// Same static/live split as marketHref; the #intelligence anchor id is
// rendered by DeskIntelligencePanel on both detail routes.
export function marketIntelHref(slug: string): string {
  return `${marketHref(slug)}#intelligence`;
}

// Same split for AI-brief entry points: catalog slugs have prerendered
// /research/brief/[slug] pages; live slugs resolve via /research/brief?slug=.
export function briefHref(slug: string): string {
  if (STATIC_SLUGS.has(slug)) return `/research/brief/${slug}`;
  return `/research/brief?slug=${encodeURIComponent(slug)}`;
}
