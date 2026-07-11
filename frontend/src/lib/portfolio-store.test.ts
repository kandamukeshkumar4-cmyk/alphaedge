import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PAPER_BALANCE } from "./mock-data";
import {
  placeOrder,
  readPortfolio,
  resetPortfolio,
  subscribePortfolio,
} from "./portfolio-store";

// portfolio-store is client-only (guards on `typeof window`). The vitest env is
// `node`, so we install a minimal window + localStorage + event bus to exercise
// the real persistence/mutation path (the paper "trade flow" helper).
type Listener = () => void;

function installFakeWindow() {
  const store = new Map<string, string>();
  const listeners: Record<string, Listener[]> = {};
  const win = {
    localStorage: {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    },
    addEventListener: (type: string, cb: Listener) => {
      (listeners[type] ??= []).push(cb);
    },
    removeEventListener: (type: string, cb: Listener) => {
      listeners[type] = (listeners[type] ?? []).filter((f) => f !== cb);
    },
    dispatchEvent: (evt: { type: string }) => {
      (listeners[evt.type] ?? []).forEach((f) => f());
      return true;
    },
  };
  vi.stubGlobal("window", win);
  vi.stubGlobal(
    "CustomEvent",
    class {
      type: string;
      constructor(type: string) {
        this.type = type;
      }
    },
  );
  return { store };
}

beforeEach(() => {
  installFakeWindow();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readPortfolio", () => {
  it("returns the paper defaults when nothing is stored", () => {
    const p = readPortfolio();
    expect(p.balance).toBe(PAPER_BALANCE);
    expect(p.positions).toEqual([]);
    expect(p.history).toEqual([]);
  });

  it("falls back to defaults on corrupt JSON", () => {
    window.localStorage.setItem("alphaedge.portfolio.v1", "{not-json");
    expect(readPortfolio().balance).toBe(PAPER_BALANCE);
  });
});

describe("placeOrder", () => {
  it("rejects a non-positive share quantity", () => {
    const res = placeOrder({
      slug: "pm-x",
      market: "M",
      outcome: "YES",
      side: "YES",
      shares: 0,
      price: 0.5,
    });
    expect(res.ok).toBe(false);
    expect(res.message).toMatch(/quantity/i);
    expect(readPortfolio().positions).toHaveLength(0);
  });

  it("rejects an order that exceeds the paper balance", () => {
    const res = placeOrder({
      slug: "pm-x",
      market: "M",
      outcome: "YES",
      side: "YES",
      shares: 1_000_000,
      price: 0.9,
    });
    expect(res.ok).toBe(false);
    expect(res.message).toMatch(/insufficient/i);
  });

  it("fills a valid order: deducts balance, adds position + history", () => {
    const res = placeOrder({
      slug: "pm-x",
      market: "Lakers win",
      outcome: "YES",
      side: "YES",
      shares: 100,
      price: 0.6,
    });
    expect(res.ok).toBe(true);
    expect(res.message).toBe("Filled 100 YES @ 60¢");
    const p = readPortfolio();
    expect(p.balance).toBeCloseTo(PAPER_BALANCE - 60, 6);
    expect(p.positions).toHaveLength(1);
    expect(p.positions[0]).toMatchObject({ slug: "pm-x", side: "YES", shares: 100 });
    expect(p.history).toHaveLength(1);
  });

  it("prepends newest positions and notifies subscribers", () => {
    const cb = vi.fn();
    const unsub = subscribePortfolio(cb);
    placeOrder({ slug: "a", market: "A", outcome: "YES", side: "YES", shares: 1, price: 0.1 });
    placeOrder({ slug: "b", market: "B", outcome: "NO", side: "NO", shares: 1, price: 0.1 });
    expect(cb).toHaveBeenCalledTimes(2);
    expect(readPortfolio().positions[0].slug).toBe("b");
    unsub();
    placeOrder({ slug: "c", market: "C", outcome: "YES", side: "YES", shares: 1, price: 0.1 });
    // No further callbacks after unsubscribe.
    expect(cb).toHaveBeenCalledTimes(2);
  });
});

describe("resetPortfolio", () => {
  it("restores the default balance and clears positions", () => {
    placeOrder({ slug: "a", market: "A", outcome: "YES", side: "YES", shares: 10, price: 0.5 });
    expect(readPortfolio().positions).toHaveLength(1);
    resetPortfolio();
    const p = readPortfolio();
    expect(p.balance).toBe(PAPER_BALANCE);
    expect(p.positions).toEqual([]);
  });
});
