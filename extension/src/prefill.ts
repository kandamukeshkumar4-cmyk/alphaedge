import { resolveExternalMarket, type ExternalMarketResolveResponse } from "./backend-client";
import type { ParsedSupportedMarket } from "./platforms";

type Fetcher = (url: string, init?: RequestInit) => Promise<Response>;

export type MarketPrefill = {
  title: string;
  category?: string;
  closeAt?: string;
  marketImpliedProbability: number | null;
  snapshotSource: "server" | "manual" | "unavailable";
  snapshotMetadata: Record<string, unknown>;
  source: "server" | "manual" | "fallback";
  error?: string;
};

export async function prefillForMarket(input: {
  market: ParsedSupportedMarket;
  apiBase: string;
  pageTitle?: string;
  fetcher?: Fetcher;
  resolveMarket?: typeof resolveExternalMarket;
}): Promise<MarketPrefill> {
  const title = input.market.title || input.pageTitle || input.market.externalId;

  if (input.market.manualOnly) {
    return {
      title,
      marketImpliedProbability: null,
      snapshotSource: "manual",
      snapshotMetadata: {
        provider: input.market.provider,
        external_id: input.market.externalId,
        manual_only: true,
      },
      source: "manual",
    };
  }

  try {
    const resolved = await (input.resolveMarket ?? resolveExternalMarket)({
      apiBase: input.apiBase,
      url: input.market.canonicalUrl,
      title,
      fetcher: input.fetcher,
    });
    const implied = impliedProbabilityFrom(resolved);
    return {
      title: resolved.title || title,
      category: resolved.category || undefined,
      closeAt: resolved.close_at ?? undefined,
      marketImpliedProbability: implied,
      snapshotSource: implied === null ? "unavailable" : resolved.snapshot?.source ? "server" : "server",
      snapshotMetadata: {
        provider: input.market.provider,
        external_id: resolved.external_id || input.market.externalId,
        resolved_market_id: resolved.id,
        status: resolved.status,
        snapshot_source: resolved.snapshot?.source,
        ...(resolved.snapshot?.metadata ?? {}),
        ...(resolved.snapshot_metadata ?? {}),
      },
      source: "server",
    };
  } catch (error) {
    return {
      title,
      marketImpliedProbability: null,
      snapshotSource: "unavailable",
      snapshotMetadata: {
        provider: input.market.provider,
        external_id: input.market.externalId,
        prefill_error: error instanceof Error ? error.message : "resolve-url failed",
      },
      source: "fallback",
      error: error instanceof Error ? error.message : "resolve-url failed",
    };
  }
}

export function impliedProbabilityFrom(response: ExternalMarketResolveResponse): number | null {
  const candidates = [
    response.market_implied_probability,
    response.implied_probability,
    response.snapshot?.implied_probability,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "number" && Number.isFinite(candidate) && candidate >= 0 && candidate <= 1) {
      return candidate;
    }
  }
  return null;
}
