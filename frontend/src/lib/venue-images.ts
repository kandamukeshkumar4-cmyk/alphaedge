// Loop V78 (N2) — venue image allowlist. Market/outcome imagery is ONLY ever
// loaded from the CDNs of the venues we ingest from; an arbitrary URL in a
// payload must never be hotlinked.
//
// Verified hosts (checked live against the venue APIs 2026-07-20):
// - Polymarket Gamma `image`/`icon` fields are served from
//   `polymarket-upload.s3.us-east-2.amazonaws.com`.
// - Kalshi's trade API exposes NO per-market image field (verified against
//   /trade-api/v2/markets) and our Kalshi ingest stores no image URLs, so
//   there is no Kalshi image host to allow — Kalshi markets use the glyph
//   fallback by design.
//
// next.config.ts consumes this list for images.remotePatterns; VenueImage
// consumes it as the runtime guard for plain <img> renders (remotePatterns
// does not apply to <img>). Keep both in sync via this single module.
export const VENUE_IMAGE_HOSTS = [
  "polymarket-upload.s3.us-east-2.amazonaws.com",
] as const;

/** True only for https URLs on an allowlisted venue CDN host. */
export function isVenueImageUrl(value: string | null | undefined): value is string {
  if (!value) {
    return false;
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return false;
  }
  if (parsed.protocol !== "https:") {
    return false;
  }
  return (VENUE_IMAGE_HOSTS as readonly string[]).includes(parsed.hostname);
}
