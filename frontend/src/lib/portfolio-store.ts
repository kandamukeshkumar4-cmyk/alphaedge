// Tiny localStorage-backed paper-trading store so the demo UI actually
// persists trades, balance, and positions across pages. Client-only.

import { PAPER_BALANCE } from "./mock-data";

export type Position = {
  id: string;
  slug: string;
  market: string;
  outcome: string;
  side: "YES" | "NO";
  shares: number;
  entryPrice: number;
  currentPrice: number;
  ts: number;
};

export type PortfolioState = {
  balance: number;
  positions: Position[];
  history: Position[];
};

const KEY = "alphaedge.portfolio.v1";
const EVENT = "alphaedge:portfolio";

function defaults(): PortfolioState {
  return { balance: PAPER_BALANCE, positions: [], history: [] };
}

export function readPortfolio(): PortfolioState {
  if (typeof window === "undefined") return defaults();
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return defaults();
    const parsed = JSON.parse(raw) as PortfolioState;
    return {
      balance: typeof parsed.balance === "number" ? parsed.balance : PAPER_BALANCE,
      positions: parsed.positions ?? [],
      history: parsed.history ?? [],
    };
  } catch {
    return defaults();
  }
}

function write(state: PortfolioState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(state));
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function placeOrder(input: {
  slug: string;
  market: string;
  outcome: string;
  side: "YES" | "NO";
  shares: number;
  price: number;
}): { ok: boolean; message: string } {
  const state = readPortfolio();
  const cost = input.price * input.shares;
  if (input.shares <= 0) return { ok: false, message: "Enter a share quantity" };
  if (cost > state.balance)
    return { ok: false, message: "Insufficient paper balance" };

  const position: Position = {
    id: `${Date.now()}-${Math.round(Math.random() * 1e6)}`,
    slug: input.slug,
    market: input.market,
    outcome: input.outcome,
    side: input.side,
    shares: input.shares,
    entryPrice: input.price,
    currentPrice: input.price,
    ts: Date.now(),
  };

  state.balance -= cost;
  state.positions = [position, ...state.positions];
  state.history = [position, ...state.history].slice(0, 100);
  write(state);
  return { ok: true, message: `Filled ${input.shares} ${input.side} @ ${Math.round(input.price * 100)}¢` };
}

export function resetPortfolio() {
  write(defaults());
}

export function subscribePortfolio(cb: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handler = () => cb();
  window.addEventListener(EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}
