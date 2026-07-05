import { formatCompactUSD, pct, type Market, type RankRow } from "./mock-data";

function pricePct(m: Market): string {
  const p = m.outcomes[0]?.price ?? 0.5;
  return pct(p);
}

export function liveTrendingRows(markets: Market[]): RankRow[] {
  const live = markets.filter((m) => m.source === "polymarket" || m.source === "kalshi");
  const pool = live.length ? live : markets;
  return [...pool]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 6)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      value: pricePct(m),
      delta: m.trendDelta,
    }));
}

export function liveTopMoverRows(markets: Market[]): RankRow[] {
  const live = markets.filter((m) => m.source === "polymarket" || m.source === "kalshi");
  const pool = live.length ? live : markets;
  return [...pool]
    .map((m) => ({ m, move: Math.abs(m.trendDelta) }))
    .sort((a, b) => b.move - a.move)
    .slice(0, 5)
    .map(({ m }) => ({
      slug: m.slug,
      title: m.title,
      value: pricePct(m),
      delta: m.trendDelta,
    }));
}

export function liveNewRows(markets: Market[]): RankRow[] {
  const live = markets.filter((m) => m.source === "polymarket" || m.source === "kalshi");
  const pool = live.length ? live : markets;
  return [...pool]
    .sort((a, b) => Date.parse(b.endsAt) - Date.parse(a.endsAt))
    .slice(0, 5)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      value: pricePct(m),
      delta: 0,
    }));
}

export function liveHighestVolumeRows(markets: Market[]): RankRow[] {
  const live = markets.filter((m) => m.source === "polymarket" || m.source === "kalshi");
  const pool = live.length ? live : markets;
  return [...pool]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 6)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      value: formatCompactUSD(m.volume),
      delta: 0,
    }));
}
