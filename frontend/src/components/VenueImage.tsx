"use client";

import { useState, type ReactNode } from "react";

import { isVenueImageUrl } from "@/lib/venue-images";

type VenueImageProps = {
  /** Venue image URL (Market.image_url from the venue's own image field). */
  src: string | null | undefined;
  alt: string;
  className?: string;
  /** Rendered when the URL is missing, not on the venue allowlist, or fails
   * to load — the honest glyph token, never a fabricated image. */
  fallback: ReactNode;
};

/**
 * Loop V78 (N2) — venue-only image with glyph fallback.
 *
 * Plain <img> on purpose: the Azure SWA deploy uses `output: "export"`, where
 * the next/image optimizer is unavailable. The runtime allowlist guard
 * (isVenueImageUrl) is what actually keeps arbitrary payload URLs from being
 * hotlinked; next.config images.remotePatterns mirrors the same host list.
 */
export function VenueImage({ src, alt, className, fallback }: VenueImageProps) {
  // Keyed by src so a later, different URL gets a fresh attempt.
  const [erroredSrc, setErroredSrc] = useState<string | null>(null);
  if (!isVenueImageUrl(src) || src === erroredSrc) {
    return <>{fallback}</>;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static-export deploy has no next/image optimizer; allowlist-guarded venue CDN only
    <img
      src={src}
      alt={alt}
      className={className}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setErroredSrc(src)}
    />
  );
}
