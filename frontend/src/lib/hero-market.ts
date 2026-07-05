import type { Market, MarketOutcome } from "./mock-data";

/** Kalshi-only hero carousel for the landing page. */
export function pickHeroMarkets(all: Market[]): Market[] {
  const kalshi = all.filter(
    (m) => (m.source === "kalshi" || m.slug.startsWith("ks-")) && isLiveMirror(m),
  );
  const sortedKalshi = groupKalshiMatches(kalshi);
  if (sortedKalshi.length > 0) {
    return sortedKalshi.slice(0, 4);
  }
  return [];
}

function groupKalshiMatches(markets: Market[]): Market[] {
  const byEvent = new Map<string, Market[]>();
  for (const m of markets) {
    const key = kalshiEventKey(m.slug);
    const list = byEvent.get(key) ?? [];
    list.push(m);
    byEvent.set(key, list);
  }

  const heroes: Market[] = [];
  for (const siblings of byEvent.values()) {
    if (siblings.length < 2) {
      heroes.push(siblings[0]);
      continue;
    }
    const grouped = buildKalshiMatchHero(siblings);
    if (grouped) heroes.push(grouped);
  }

  return heroes.sort((a, b) => b.volume - a.volume);
}

function kalshiEventKey(slug: string): string {
  if (!slug.startsWith("ks-")) return slug;
  const idx = slug.lastIndexOf("-");
  return idx > 3 ? slug.slice(0, idx) : slug;
}

function buildKalshiMatchHero(siblings: Market[]): Market | null {
  const anchor = siblings[0];
  if (!anchor) return null;

  let teamToneAssigned = false;
  const outcomes: MarketOutcome[] = siblings.slice(0, 4).map((m) => {
    const label = kalshiOutcomeLabel(m);
    const yes = m.outcomes[0]?.price ?? 0.5;
    let tone: MarketOutcome["tone"] = "danger";
    if (/tie|draw/i.test(label)) {
      tone = "muted";
    } else if (!teamToneAssigned) {
      tone = "primary";
      teamToneAssigned = true;
    }
    return {
      id: m.slug,
      label,
      emoji: outcomeEmoji(label),
      price: yes,
      prevPrice: yes,
      tone,
    };
  });

  return {
    ...anchor,
    title: anchor.title,
    question: `Live Kalshi mirror · ${anchor.title}`,
    outcomes,
    marketCount: siblings.length,
    source: "kalshi",
  };
}

function kalshiOutcomeLabel(m: Market): string {
  const q = m.question.split("—")[0]?.trim();
  if (q) return q;
  const tail = m.slug.split("-").pop()?.toUpperCase();
  if (tail === "TIE") return "Tie";
  if (tail === "CAN") return "Canada";
  return tail ?? m.outcomes[0]?.label ?? "YES";
}

function outcomeEmoji(label: string): string {
  if (/tie/i.test(label)) return "🤝";
  return "⚽";
}

/** Group same-day fifwc slugs into one Kalshi-style multi-outcome hero when possible. */
function buildMatchHeroMarket(candidates: Market[]): Market | null {
  const anchor = candidates[0];
  if (!anchor) return null;

  const dateMatch = anchor.slug.match(/(\d{4}-\d{2}-\d{2})/);
  if (!dateMatch) return anchor;

  const date = dateMatch[1];
  const siblings = candidates.filter((m) => m.slug.includes(date));
  if (siblings.length < 2) return anchor;

  const tones: MarketOutcome["tone"][] = ["primary", "muted", "danger", "accent"];
  const outcomes: MarketOutcome[] = siblings.slice(0, 4).map((m, i) => {
    const yes = m.outcomes[0]?.price ?? 0.5;
    return {
      id: m.slug,
      label: outcomeLabelFromMarket(m),
      emoji: m.icon || "⚽",
      price: yes,
      prevPrice: yes,
      tone: tones[i] ?? "muted",
    };
  });

  return {
    ...anchor,
    title: matchTitleFromMarkets(siblings, date),
    question: `Live World Cup match · ${date}`,
    outcomes,
    marketCount: siblings.length,
    source: "polymarket",
  };
}

function outcomeLabelFromMarket(m: Market): string {
  const t = m.title;
  if (/draw/i.test(t)) return "Draw";
  const win = t.match(/Will (.+?) win/i);
  if (win?.[1]) return win[1].replace(/ on .+$/, "").trim();
  return m.outcomes[0]?.label ?? "YES";
}

function matchTitleFromMarkets(siblings: Market[], date: string): string {
  const labels = siblings.map(outcomeLabelFromMarket).filter((l) => l !== "Draw");
  if (labels.length >= 2) {
    return `${labels[0]} vs ${labels[1]}`;
  }
  return siblings[0]?.title ?? `World Cup · ${date}`;
}

export function isKalshiWcMatchSlug(slug: string): boolean {
  return slug.startsWith("ks-kxwcgame-");
}

/** Grouped Kalshi FIFA match cards for the home grid (excludes long-shot winner markets). */
export function pickHomeGridMarkets(all: Market[], limit = 20): Market[] {
  const kalshi = all.filter(
    (m) => m.source === "kalshi" && isKalshiWcMatchSlug(m.slug),
  );
  if (!kalshi.length) return [];

  return groupKalshiMatches(kalshi)
    .sort((a, b) => b.volume - a.volume)
    .slice(0, limit);
}

export function isLiveMirror(market: Market): boolean {
  return market.source === "polymarket" || market.source === "kalshi";
}

export function isKalshiMatchCard(market: Market): boolean {
  return (
    market.source === "kalshi" &&
    isKalshiWcMatchSlug(market.slug) &&
    market.outcomes.length >= 2
  );
}

/** @deprecated use isLiveMirror */
export function isLivePolymarket(market: Market): boolean {
  return isLiveMirror(market);
}
