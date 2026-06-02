// Rich, deterministic mock data for the AlphaEdge UI.
// Deterministic so Next.js static export + hydration stay stable; the live
// "tick" engine (see useLiveMarket) layers random motion on top client-side.

export type Category =
  | "Sports"
  | "Politics"
  | "Crypto"
  | "Culture"
  | "Economics";

export type OutcomeTone = "primary" | "danger" | "accent" | "gold" | "muted";

export type MarketOutcome = {
  id: string;
  label: string;
  emoji: string;
  price: number; // 0..1
  prevPrice: number;
  tone: OutcomeTone;
};

export type Candle = {
  time: number; // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
};

export type BookLevel = { price: number; size: number };

export type Trade = {
  id: string;
  user: string;
  side: "YES" | "NO";
  outcome: string;
  price: number;
  shares: number;
  tsOffsetSec: number; // seconds ago (deterministic)
};

export type Holder = {
  user: string;
  side: "YES" | "NO";
  shares: number;
  tone: OutcomeTone;
};

export type AIForecast = {
  prob: number;
  confidence: number;
  edge: number;
  brier: number;
  reasoning: string;
};

export type Comment = {
  id: string;
  user: string;
  tone: OutcomeTone;
  body: string;
  tsOffsetSec: number;
  likes: number;
};

export type Market = {
  id: string;
  slug: string;
  category: Category;
  icon: string;
  title: string;
  question: string;
  endsAt: string;
  volume: number;
  traders: number;
  marketCount: number;
  trendDelta: number; // % change rank delta
  outcomes: MarketOutcome[];
  forecast: AIForecast;
  bids: BookLevel[]; // YES bids
  asks: BookLevel[]; // YES asks
  description: string;
  resolution: string;
  trades: Trade[];
  holders: Holder[];
  comments: Comment[];
  seed: number;
};

export const CATEGORIES: Category[] = [
  "Sports",
  "Politics",
  "Crypto",
  "Culture",
  "Economics",
];

// ---------- seeded PRNG ----------
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const USERS = [
  "alpha_quant",
  "edgeHunter",
  "marketGuru",
  "brierBeast",
  "kelly_max",
  "lineMover",
  "noFloor",
  "yesFloor",
  "deltaOne",
  "calibrated",
  "tailRisk",
  "sharpKing",
];

const TONES: OutcomeTone[] = ["primary", "danger", "accent", "gold", "muted"];

// ---------- generators ----------
export function generateCandles(
  slug: string,
  points: number,
  endPrice: number,
  stepSec: number,
): Candle[] {
  const rand = mulberry32(hashSeed(slug));
  const now = Math.floor(Date.UTC(2026, 5, 2, 17, 0, 0) / 1000);
  // walk backwards from endPrice so the last candle matches the card price
  const closes: number[] = [endPrice];
  for (let i = 1; i < points; i += 1) {
    const drift = (rand() - 0.5) * 0.035;
    const prev = closes[0];
    let next = prev - drift;
    next = Math.min(0.94, Math.max(0.06, next));
    closes.unshift(next);
  }
  const candles: Candle[] = [];
  for (let i = 0; i < points; i += 1) {
    const close = closes[i];
    const open = i === 0 ? close : closes[i - 1];
    const wig = 0.012 + rand() * 0.02;
    const high = Math.min(0.97, Math.max(open, close) + wig * rand());
    const low = Math.max(0.03, Math.min(open, close) - wig * rand());
    candles.push({
      time: now - (points - 1 - i) * stepSec,
      open,
      high,
      low,
      close,
    });
  }
  return candles;
}

function makeBook(
  rand: () => number,
  mid: number,
): { bids: BookLevel[]; asks: BookLevel[] } {
  const bids: BookLevel[] = [];
  const asks: BookLevel[] = [];
  for (let i = 0; i < 8; i += 1) {
    bids.push({
      price: Math.max(0.01, mid - 0.01 * (i + 1)),
      size: Math.round(400 + rand() * 4200),
    });
    asks.push({
      price: Math.min(0.99, mid + 0.01 * (i + 1)),
      size: Math.round(400 + rand() * 4200),
    });
  }
  return { bids, asks };
}

function makeTrades(rand: () => number, outcomes: MarketOutcome[]): Trade[] {
  const list: Trade[] = [];
  for (let i = 0; i < 14; i += 1) {
    const oc = outcomes[Math.floor(rand() * outcomes.length)];
    const side = rand() > 0.5 ? "YES" : "NO";
    list.push({
      id: `t-${i}`,
      user: USERS[Math.floor(rand() * USERS.length)],
      side,
      outcome: oc.label,
      price: side === "YES" ? oc.price : 1 - oc.price,
      shares: Math.round(5 + rand() * 480),
      tsOffsetSec: Math.round(20 + i * (40 + rand() * 90)),
    });
  }
  return list.sort((a, b) => a.tsOffsetSec - b.tsOffsetSec);
}

function makeHolders(rand: () => number): Holder[] {
  return Array.from({ length: 8 }, (_, i): Holder => ({
    user: USERS[(i * 3) % USERS.length],
    side: rand() > 0.45 ? "YES" : "NO",
    shares: Math.round(800 + rand() * 24000),
    tone: TONES[i % TONES.length],
  })).sort((a, b) => b.shares - a.shares);
}

function makeComments(rand: () => number): Comment[] {
  const bodies = [
    "Model edge looks real here, fading the book.",
    "Closing line value is positive — staying YES.",
    "Volume spiked after the injury report.",
    "Brier on this category has been excellent lately.",
    "Taking the other side, calibration says overpriced.",
    "Nice resting bid wall at the round number.",
  ];
  return Array.from({ length: 5 }, (_, i) => ({
    id: `c-${i}`,
    user: USERS[(i * 5 + 1) % USERS.length],
    tone: TONES[i % TONES.length],
    body: bodies[i % bodies.length],
    tsOffsetSec: Math.round(120 + i * (200 + rand() * 400)),
    likes: Math.round(rand() * 48),
  }));
}

type Spec = {
  slug: string;
  category: Category;
  icon: string;
  title: string;
  question: string;
  endsInHours: number;
  volume: number;
  traders: number;
  marketCount: number;
  outcomes: Array<{ label: string; emoji: string; price: number }>;
  reasoning: string;
  confidence: number;
  brier: number;
  description: string;
  resolution: string;
};

const SPECS: Spec[] = [
  {
    slug: "nba-2025-01-15-lal-bos",
    category: "Sports",
    icon: "🏀",
    title: "Lakers vs Celtics",
    question: "Will the Lakers win?",
    endsInHours: 6,
    volume: 2_413_000,
    traders: 3214,
    marketCount: 3,
    outcomes: [
      { label: "Lakers", emoji: "🟣", price: 0.65 },
      { label: "Celtics", emoji: "🟢", price: 0.35 },
    ],
    reasoning:
      "Strong home form and a favorable rest differential; Celtics missing a key rotation guard. Model leans Lakers above the implied book.",
    confidence: 0.84,
    brier: 0.1024,
    description:
      "Head-to-head paper market on the Jan 15 Lakers vs Celtics matchup. YES resolves if the Lakers win.",
    resolution: "Resolves YES if the Lakers win the game, otherwise NO.",
  },
  {
    slug: "nba-warriors-playoff-seed",
    category: "Sports",
    icon: "🏀",
    title: "Warriors top-6 seed",
    question: "Will the Warriors finish top 6 in the West?",
    endsInHours: 52,
    volume: 1_182_000,
    traders: 2110,
    marketCount: 2,
    outcomes: [
      { label: "Top 6", emoji: "🔵", price: 0.58 },
      { label: "Outside", emoji: "⚪", price: 0.42 },
    ],
    reasoning:
      "Schedule strength eases over the next two weeks; net rating trending up. Slight model edge to the YES side.",
    confidence: 0.71,
    brier: 0.1331,
    description: "Will the Golden State Warriors finish the regular season in the top 6 of the Western Conference?",
    resolution: "Resolves YES if final seed is 6 or better.",
  },
  {
    slug: "soccer-denmark-congo",
    category: "Sports",
    icon: "⚽",
    title: "Denmark vs Congo DR",
    question: "Match result?",
    endsInHours: 30,
    volume: 293_000,
    traders: 880,
    marketCount: 3,
    outcomes: [
      { label: "Denmark", emoji: "🇩🇰", price: 0.64 },
      { label: "Congo DR", emoji: "🇨🇩", price: 0.17 },
      { label: "Tie", emoji: "⚪", price: 0.22 },
    ],
    reasoning:
      "Denmark's xG advantage at home is large; draw is fairly priced. Model marginally fades the favorite on fatigue.",
    confidence: 0.6,
    brier: 0.182,
    description: "International friendly result market.",
    resolution: "Resolves to the winning side at full time; Tie if drawn.",
  },
  {
    slug: "elect-la-mayor-2026",
    category: "Politics",
    icon: "🗳️",
    title: "LA Mayor winner",
    question: "Will the incumbent win re-election?",
    endsInHours: 240,
    volume: 4_120_000,
    traders: 5402,
    marketCount: 4,
    outcomes: [
      { label: "Incumbent", emoji: "🟦", price: 0.66 },
      { label: "Challenger", emoji: "🟥", price: 0.34 },
    ],
    reasoning:
      "Polling cross-tabs and fundraising favor the incumbent; challenger momentum slowing. Model in line with book.",
    confidence: 0.78,
    brier: 0.108,
    description: "2026 Los Angeles mayoral election market.",
    resolution: "Resolves to the certified winner of the election.",
  },
  {
    slug: "elect-2028-dem-nominee",
    category: "Politics",
    icon: "🇺🇸",
    title: "2028 Democratic nominee",
    question: "Will the frontrunner be the nominee?",
    endsInHours: 720,
    volume: 1_194_000,
    traders: 4500,
    marketCount: 45,
    outcomes: [
      { label: "Frontrunner", emoji: "🔵", price: 0.23 },
      { label: "Field", emoji: "⚪", price: 0.77 },
    ],
    reasoning:
      "Early and wide field; frontrunner share historically overpriced this far out. Model fades to the field.",
    confidence: 0.55,
    brier: 0.2,
    description: "2028 Democratic presidential nomination market.",
    resolution: "Resolves YES if the listed frontrunner becomes the nominee.",
  },
  {
    slug: "crypto-btc-friday-5pm",
    category: "Crypto",
    icon: "₿",
    title: "BTC above $88k Friday 5pm",
    question: "Will BTC close above $88,000?",
    endsInHours: 18,
    volume: 3_880_000,
    traders: 6120,
    marketCount: 6,
    outcomes: [
      { label: "Above", emoji: "🟢", price: 0.42 },
      { label: "Below", emoji: "🔴", price: 0.58 },
    ],
    reasoning:
      "Realized vol elevated; spot drifting under the strike. Model slightly favors Below into the close.",
    confidence: 0.69,
    brier: 0.149,
    description: "Will BTC/USD settle above $88,000 at the Friday 5pm ET reference?",
    resolution: "Resolves to the reference result for this paper market.",
  },
  {
    slug: "crypto-eth-100k-eoy",
    category: "Crypto",
    icon: "Ξ",
    title: "ETH > $5k by EOY",
    question: "Will ETH exceed $5,000 this year?",
    endsInHours: 1200,
    volume: 920_000,
    traders: 2890,
    marketCount: 4,
    outcomes: [
      { label: "Yes", emoji: "🟢", price: 0.55 },
      { label: "No", emoji: "🔴", price: 0.45 },
    ],
    reasoning:
      "ETF flows constructive; supply burn steady. Model edge mildly positive to YES.",
    confidence: 0.62,
    brier: 0.158,
    description: "Will ETH/USD print above $5,000 before year end?",
    resolution: "Resolves YES if ETH trades >= $5,000 at any reference before EOY.",
  },
  {
    slug: "culture-gta6-trailer",
    category: "Culture",
    icon: "🎮",
    title: "GTA VI trailer before August",
    question: "Will the next trailer drop before August?",
    endsInHours: 400,
    volume: 226_000,
    traders: 1430,
    marketCount: 6,
    outcomes: [
      { label: "Before Aug", emoji: "🟢", price: 0.74 },
      { label: "After", emoji: "🔴", price: 0.26 },
    ],
    reasoning:
      "Marketing cadence and retailer leaks point to an early-summer drop. Model leans YES.",
    confidence: 0.66,
    brier: 0.142,
    description: "Will Rockstar release the next GTA VI trailer before August 1?",
    resolution: "Resolves YES on an official trailer release before the deadline.",
  },
  {
    slug: "culture-love-island-elim",
    category: "Culture",
    icon: "🌴",
    title: "Love Island S8E1 elimination",
    question: "Who gets eliminated first?",
    endsInHours: 12,
    volume: 43_672,
    traders: 540,
    marketCount: 9,
    outcomes: [
      { label: "Gabriel", emoji: "🧑", price: 0.27 },
      { label: "Aniya", emoji: "👩", price: 0.05 },
      { label: "Melanie", emoji: "👩‍🦰", price: 0.03 },
      { label: "Field", emoji: "⚪", price: 0.65 },
    ],
    reasoning:
      "Edit and social sentiment skew negative for Gabriel; long tail across the field.",
    confidence: 0.5,
    brier: 0.21,
    description: "First elimination market for Love Island USA S8E1.",
    resolution: "Resolves to the first contestant eliminated.",
  },
  {
    slug: "econ-cpi-above-3",
    category: "Economics",
    icon: "📈",
    title: "CPI above 3.0% YoY",
    question: "Will headline CPI print above 3.0%?",
    endsInHours: 96,
    volume: 612_000,
    traders: 1980,
    marketCount: 3,
    outcomes: [
      { label: "Above 3%", emoji: "🔴", price: 0.4 },
      { label: "At/Below", emoji: "🟢", price: 0.6 },
    ],
    reasoning:
      "Base effects and shelter disinflation argue for a sub-3 print; model favors At/Below.",
    confidence: 0.73,
    brier: 0.121,
    description: "Will the next headline CPI release print above 3.0% year over year?",
    resolution: "Resolves to the official BLS release.",
  },
  {
    slug: "econ-fed-cut-march",
    category: "Economics",
    icon: "🏦",
    title: "Fed cut at next meeting",
    question: "Will the Fed cut rates at the next meeting?",
    endsInHours: 300,
    volume: 1_530_000,
    traders: 3340,
    marketCount: 2,
    outcomes: [
      { label: "Cut", emoji: "🟢", price: 0.31 },
      { label: "Hold", emoji: "🔴", price: 0.69 },
    ],
    reasoning:
      "Dot plot and recent speak lean hold; futures-implied odds align. Model in line.",
    confidence: 0.8,
    brier: 0.114,
    description: "Will the FOMC cut the target range at its next scheduled meeting?",
    resolution: "Resolves to the official FOMC decision.",
  },
];

function buildMarket(spec: Spec): Market {
  const rand = mulberry32(hashSeed(spec.slug));
  const outcomes: MarketOutcome[] = spec.outcomes.map((o, i) => ({
    id: `${spec.slug}-o${i}`,
    label: o.label,
    emoji: o.emoji,
    price: o.price,
    prevPrice: Math.min(0.97, Math.max(0.03, o.price + (rand() - 0.5) * 0.04)),
    tone: TONES[i % TONES.length],
  }));
  const yesPrice = outcomes[0].price;
  const book = makeBook(rand, yesPrice);
  const edge = spec.outcomes[0].price - spec.confidence * spec.outcomes[0].price;
  return {
    id: hashSeed(spec.slug).toString(),
    slug: spec.slug,
    category: spec.category,
    icon: spec.icon,
    title: spec.title,
    question: spec.question,
    endsAt: new Date(
      Date.UTC(2026, 5, 2, 17, 0, 0) + spec.endsInHours * 3600 * 1000,
    ).toISOString(),
    volume: spec.volume,
    traders: spec.traders,
    marketCount: spec.marketCount,
    trendDelta: Math.round((rand() - 0.4) * 90),
    outcomes,
    forecast: {
      prob: Math.min(0.97, yesPrice + (rand() - 0.3) * 0.08),
      confidence: spec.confidence,
      edge: Math.max(-0.06, Math.min(0.08, edge + (rand() - 0.5) * 0.02)),
      brier: spec.brier,
      reasoning: spec.reasoning,
    },
    bids: book.bids,
    asks: book.asks,
    description: spec.description,
    resolution: spec.resolution,
    trades: makeTrades(rand, outcomes),
    holders: makeHolders(rand),
    comments: makeComments(rand),
    seed: hashSeed(spec.slug),
  };
}

export const MARKETS: Market[] = SPECS.map(buildMarket);

export function getMarket(slug: string): Market | undefined {
  return MARKETS.find((m) => m.slug === slug);
}

export function marketsByCategory(): Array<{ category: Category; markets: Market[] }> {
  return CATEGORIES.map((category) => ({
    category,
    markets: MARKETS.filter((m) => m.category === category),
  })).filter((g) => g.markets.length > 0);
}

// ---------- ranked rails ----------
export type RankRow = {
  slug: string;
  title: string;
  value: string;
  delta: number; // positive/negative for ▲▼; 0 = none
  badge?: string;
};

export function trendingRows(): RankRow[] {
  return [...MARKETS]
    .sort((a, b) => b.traders - a.traders)
    .slice(0, 6)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      value: `${Math.round(m.outcomes[0].price * 100)}%`,
      delta: m.trendDelta,
    }));
}

export function topMoverRows(): RankRow[] {
  return [...MARKETS]
    .map((m) => ({ m, move: Math.abs(m.trendDelta) }))
    .sort((a, b) => b.move - a.move)
    .slice(0, 5)
    .map(({ m }) => ({
      slug: m.slug,
      title: m.title,
      value: `${Math.round(m.outcomes[0].price * 100)}%`,
      delta: m.trendDelta,
    }));
}

export function newRows(): RankRow[] {
  return [...MARKETS]
    .sort((a, b) => a.volume - b.volume)
    .slice(0, 5)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      value: `${Math.round(m.outcomes[0].price * 100)}%`,
      delta: 0,
    }));
}

export function highestVolumeRows(): RankRow[] {
  return [...MARKETS]
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 6)
    .map((m) => ({
      slug: m.slug,
      title: m.title,
      value: formatCompactUSD(m.volume),
      delta: 0,
    }));
}

// ---------- formatting helpers ----------
export function formatCompactUSD(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export function formatUSD(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function cents(price: number): string {
  return `${Math.round(price * 100)}¢`;
}

export function pct(price: number): string {
  return `${Math.round(price * 100)}%`;
}

export function multiplier(price: number): string {
  if (price <= 0) return "—";
  return `${(1 / price).toFixed(2)}x`;
}

export function timeUntil(iso: string): string {
  const now = Date.UTC(2026, 5, 2, 17, 0, 0);
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return "closed";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  if (h >= 48) return `${Math.floor(h / 24)}d`;
  if (h >= 1) return `${h}h ${m}m`;
  return `${m}m`;
}

export function timeAgo(offsetSec: number): string {
  if (offsetSec < 60) return `${offsetSec}s ago`;
  if (offsetSec < 3600) return `${Math.floor(offsetSec / 60)}m ago`;
  return `${Math.floor(offsetSec / 3600)}h ago`;
}

export function toneClass(tone: OutcomeTone): string {
  switch (tone) {
    case "primary":
      return "text-primary";
    case "danger":
      return "text-danger";
    case "accent":
      return "text-accent";
    case "gold":
      return "text-gold";
    default:
      return "text-muted";
  }
}

export const PAPER_BALANCE = 100_000;
