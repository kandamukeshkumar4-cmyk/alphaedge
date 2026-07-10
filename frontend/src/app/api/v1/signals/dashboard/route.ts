import { NextResponse } from "next/server";

/**
 * Cached same-origin proxy for /api/v1/signals/dashboard.
 *
 * Next.js route handlers take precedence over next.config rewrites, so this
 * path no longer blindly forwards every browser hit (and every HF 429 HTML
 * page) to the client. A short TTL + stale-on-429 keeps /signals usable when
 * the free-tier Space ELB is rate-limiting the shared Vercel→HF edge IP.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HF_PROD_API =
  (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/+$/, "") ||
  "https://mukeshkumar007-alphaedge-api.hf.space";

const CACHE_TTL_MS = 30_000;
const STALE_MAX_MS = 5 * 60_000;

type CacheEntry = {
  at: number;
  body: string;
  contentType: string;
};

let memoryCache: CacheEntry | null = null;

function cacheHeaders(hit: "HIT" | "MISS" | "STALE"): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-AlphaEdge-Cache": hit,
    // CDN / browser: absorb repeat /signals loads across users.
    "Cache-Control": "public, s-maxage=30, stale-while-revalidate=120",
  };
}

export async function GET(request: Request): Promise<Response> {
  const now = Date.now();
  if (memoryCache && now - memoryCache.at < CACHE_TTL_MS) {
    return new NextResponse(memoryCache.body, {
      status: 200,
      headers: cacheHeaders("HIT"),
    });
  }

  const qs = new URL(request.url).search;
  const upstreamUrl = `${HF_PROD_API}/api/v1/signals/dashboard${qs}`;

  try {
    const upstream = await fetch(upstreamUrl, {
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
      headers: { Accept: "application/json" },
    });
    const body = await upstream.text();
    const contentType = upstream.headers.get("content-type") || "application/json";

    if (upstream.ok && contentType.includes("json")) {
      memoryCache = { at: now, body, contentType };
      return new NextResponse(body, {
        status: 200,
        headers: cacheHeaders("MISS"),
      });
    }

    // HF free-tier often returns HTML 429 — serve last good JSON if fresh enough.
    if (
      memoryCache &&
      now - memoryCache.at < STALE_MAX_MS &&
      (upstream.status === 429 || upstream.status >= 500)
    ) {
      return new NextResponse(memoryCache.body, {
        status: 200,
        headers: cacheHeaders("STALE"),
      });
    }

    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        "Content-Type": contentType,
        "X-AlphaEdge-Cache": "BYPASS",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    if (memoryCache && now - memoryCache.at < STALE_MAX_MS) {
      return new NextResponse(memoryCache.body, {
        status: 200,
        headers: cacheHeaders("STALE"),
      });
    }
    return NextResponse.json(
      { detail: "Signals upstream unavailable" },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
