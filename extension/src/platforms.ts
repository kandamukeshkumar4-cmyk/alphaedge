export type SupportedProvider = "polymarket" | "kalshi" | "fanduel";
export type SupportedPlatform = "polymarket" | "kalshi" | "manual";

export type ParsedSupportedMarket = {
  platform: SupportedPlatform;
  provider: SupportedProvider;
  externalId: string;
  canonicalUrl: string;
  manualOnly: boolean;
  title: string;
};

const POLYMARKET_HOSTS = new Set(["polymarket.com", "www.polymarket.com"]);
const KALSHI_HOSTS = new Set(["kalshi.com", "www.kalshi.com"]);
const FANDUEL_HOSTS = new Set(["sportsbook.fanduel.com"]);

export function parseSupportedUrl(url: string, title = ""): ParsedSupportedMarket | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  const host = parsed.hostname.toLowerCase();
  const path = parsed.pathname || "/";

  if (POLYMARKET_HOSTS.has(host)) {
    const match = path.match(/^\/(?:event|market)\/([A-Za-z0-9\-_]+)/);
    if (!match) {
      return null;
    }
    const externalId = match[1].toLowerCase();
    return {
      platform: "polymarket",
      provider: "polymarket",
      externalId,
      canonicalUrl: `https://polymarket.com/event/${externalId}`,
      manualOnly: false,
      title,
    };
  }

  if (KALSHI_HOSTS.has(host)) {
    const match = path.match(/^\/markets\/([A-Za-z0-9\-_/]+)/);
    if (!match) {
      return null;
    }
    const externalId = match[1].replace(/^\/+|\/+$/g, "").toLowerCase();
    return {
      platform: "kalshi",
      provider: "kalshi",
      externalId,
      canonicalUrl: `https://kalshi.com/markets/${externalId}`,
      manualOnly: false,
      title,
    };
  }

  if (FANDUEL_HOSTS.has(host)) {
    const normalizedPath = path.replace(/\/+$/g, "") || "/";
    return {
      platform: "manual",
      provider: "fanduel",
      externalId: `fanduel:${host}${normalizedPath}`,
      canonicalUrl: `https://sportsbook.fanduel.com${normalizedPath}`,
      manualOnly: true,
      title,
    };
  }

  return null;
}
