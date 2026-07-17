import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clampMetric,
  decisionActionTone,
  decisionKey,
  fetchHeartbeatDecisions,
  fetchMarketContext,
  fetchPods,
  findNewDecisionKeys,
  formatDecisionTime,
  normalizePodStatus,
  sortDecisionsNewestFirst,
  type HeartbeatDecision,
} from "./pods-api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const PODS_PAYLOAD = {
  pods: [
    {
      id: "pod-001",
      name: "nba-momentum",
      status: "running",
      bankroll: 10000,
      equity: 10231.44,
      pnl_24h: 231.44,
      trades_count: 17,
      last_decision_at: "2026-07-17T09:58:00Z",
    },
    {
      id: "pod-002",
      name: "election-mean-revert",
      status: "halted",
      bankroll: 5000,
      equity: 4870.1,
      pnl_24h: -129.9,
      trades_count: 6,
      last_decision_at: null,
    },
  ],
  equity_curves: {
    "pod-001": [
      { t: "2026-07-17T09:00:00Z", equity: 10000 },
      { t: "2026-07-17T09:05:00Z", equity: 10231.44 },
    ],
  },
};

describe("pods API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchPods returns the parsed fleet payload", async () => {
    const fetcher = vi.fn(async (url: string) => {
      expect(url).toBe("https://api.example.test/api/v1/pods");
      return jsonResponse(PODS_PAYLOAD);
    });

    const result = await fetchPods({ apiBase: "https://api.example.test", fetcher });

    expect(result).toEqual({ ok: true, data: PODS_PAYLOAD });
  });

  it("fetchPods maps a 404 to an honest not-deployed result", async () => {
    const fetcher = vi.fn(async () => jsonResponse({ detail: "Not Found" }, 404));

    const result = await fetchPods({ apiBase: "https://api.example.test", fetcher });

    expect(result).toEqual({ ok: false, reason: "not-deployed" });
  });

  it("fetchPods maps other HTTP errors and network failures to unavailable", async () => {
    const httpError = await fetchPods({
      apiBase: "https://api.example.test",
      fetcher: vi.fn(async () => jsonResponse({ detail: "boom" }, 500)),
    });
    expect(httpError).toEqual({ ok: false, reason: "unavailable" });

    const networkError = await fetchPods({
      apiBase: "https://api.example.test",
      fetcher: vi.fn(async () => {
        throw new Error("connection refused");
      }),
    });
    expect(networkError).toEqual({ ok: false, reason: "unavailable" });
  });

  it("fetchPods fails closed when no API base is configured", async () => {
    const result = await fetchPods({ apiBase: "", fetcher: vi.fn() });
    expect(result).toEqual({ ok: false, reason: "unavailable" });
  });

  it("fetchHeartbeatDecisions passes an optional limit and parses decisions", async () => {
    const payload = {
      decisions: [
        {
          t: "2026-07-17T10:00:00Z",
          pod: "nba-momentum",
          market: "nba-2025-01-15-lal-bos",
          rule: "edge_threshold",
          action: "buy_yes",
          latency_ms: 182,
        },
      ],
    };
    const fetcher = vi.fn(async (url: string) => {
      expect(url).toBe(
        "https://api.example.test/api/v1/heartbeat/decisions?limit=25",
      );
      return jsonResponse(payload);
    });

    const result = await fetchHeartbeatDecisions({
      apiBase: "https://api.example.test",
      fetcher,
      limit: 25,
    });

    expect(result).toEqual({ ok: true, data: payload });
  });

  it("fetchHeartbeatDecisions omits the query string without a limit", async () => {
    const fetcher = vi.fn(async (url: string) => {
      expect(url).toBe("https://api.example.test/api/v1/heartbeat/decisions");
      return jsonResponse({ decisions: [] });
    });

    const result = await fetchHeartbeatDecisions({
      apiBase: "https://api.example.test",
      fetcher,
    });

    expect(result).toEqual({ ok: true, data: { decisions: [] } });
  });

  it("fetchMarketContext encodes the slug and parses the context payload", async () => {
    const payload = {
      whale_pressure: 0.72,
      venue_gap: 0.015,
      news_signal: 0.4,
      price_trend: 0.06,
      volume_pct: 0.81,
      captured_at: "2026-07-17T10:01:00Z",
    };
    const fetcher = vi.fn(async (url: string) => {
      expect(url).toBe(
        "https://api.example.test/api/v1/markets/nba-2025-01-15-lal-bos/context",
      );
      return jsonResponse(payload);
    });

    const result = await fetchMarketContext("nba-2025-01-15-lal-bos", {
      apiBase: "https://api.example.test",
      fetcher,
    });

    expect(result).toEqual({ ok: true, data: payload });
  });

  it("fetchMarketContext returns not-deployed on 404 and rejects an empty slug", async () => {
    const notFound = await fetchMarketContext("some-market", {
      apiBase: "https://api.example.test",
      fetcher: vi.fn(async () => jsonResponse({ detail: "Not Found" }, 404)),
    });
    expect(notFound).toEqual({ ok: false, reason: "not-deployed" });

    const empty = await fetchMarketContext("   ", {
      apiBase: "https://api.example.test",
      fetcher: vi.fn(),
    });
    expect(empty).toEqual({ ok: false, reason: "unavailable" });
  });
});

describe("pod status normalization", () => {
  it("maps the documented chip states", () => {
    expect(normalizePodStatus("running")).toBe("running");
    expect(normalizePodStatus("halted")).toBe("halted");
    expect(normalizePodStatus("flag-off")).toBe("flag-off");
  });

  it("accepts common aliases case-insensitively", () => {
    expect(normalizePodStatus("ACTIVE")).toBe("running");
    expect(normalizePodStatus("Paused")).toBe("halted");
    expect(normalizePodStatus("flag_off")).toBe("flag-off");
  });

  it("falls back to unknown for anything else", () => {
    expect(normalizePodStatus("degraded")).toBe("unknown");
    expect(normalizePodStatus("")).toBe("unknown");
    expect(normalizePodStatus(null)).toBe("unknown");
    expect(normalizePodStatus(undefined)).toBe("unknown");
  });
});

describe("decision action tone", () => {
  it("maps buy/enter/long actions to the green trade token", () => {
    expect(decisionActionTone("buy_yes")).toBe("buy");
    expect(decisionActionTone("ENTER_NO")).toBe("buy");
    expect(decisionActionTone("long")).toBe("buy");
  });

  it("maps sell/exit/close actions to the red trade token", () => {
    expect(decisionActionTone("sell_yes")).toBe("sell");
    expect(decisionActionTone("EXIT")).toBe("sell");
    expect(decisionActionTone("close_position")).toBe("sell");
  });

  it("keeps skip/hold/unknown actions neutral", () => {
    expect(decisionActionTone("skip")).toBe("neutral");
    expect(decisionActionTone("hold")).toBe("neutral");
    expect(decisionActionTone("no_trade")).toBe("neutral");
    expect(decisionActionTone("")).toBe("neutral");
    expect(decisionActionTone(null)).toBe("neutral");
  });
});

describe("decision ordering and identity", () => {
  const older: HeartbeatDecision = {
    t: "2026-07-17T09:00:00Z",
    pod: "a",
    market: "m1",
    rule: "r1",
    action: "buy_yes",
    latency_ms: 100,
  };
  const newer: HeartbeatDecision = {
    t: "2026-07-17T10:00:00Z",
    pod: "b",
    market: "m2",
    rule: "r2",
    action: "skip",
    latency_ms: 80,
  };

  it("sorts newest first without mutating the input", () => {
    const input = [older, newer];
    const sorted = sortDecisionsNewestFirst(input);
    expect(sorted[0]).toBe(newer);
    expect(sorted[1]).toBe(older);
    expect(input[0]).toBe(older);
  });

  it("treats unparseable timestamps as oldest", () => {
    const broken: HeartbeatDecision = { ...older, t: "not-a-date" };
    const sorted = sortDecisionsNewestFirst([broken, older]);
    expect(sorted[0]).toBe(older);
    expect(sorted[1]).toBe(broken);
  });

  it("builds a stable identity key per decision", () => {
    expect(decisionKey(older)).toBe(
      "2026-07-17T09:00:00Z|a|m1|r1|buy_yes",
    );
    expect(decisionKey(older)).not.toBe(decisionKey(newer));
  });
});

describe("findNewDecisionKeys", () => {
  const first: HeartbeatDecision = {
    t: "2026-07-17T10:00:00Z",
    pod: "nba-momentum",
    market: "nba-2025-01-15-lal-bos",
    rule: "edge_threshold",
    action: "buy_yes",
    latency_ms: 182,
  };
  const second: HeartbeatDecision = {
    t: "2026-07-17T10:00:05Z",
    pod: "election-mean-revert",
    market: "election-2026-senate",
    rule: "clv_guard",
    action: "skip",
    latency_ms: 94,
  };

  it("marks nothing as new on the very first load (known = null)", () => {
    // The whole list is new on first paint; blinking every row would be noise.
    expect(findNewDecisionKeys(null, [first, second]).size).toBe(0);
  });

  it("flags only decisions that were not already known", () => {
    const known = new Set([decisionKey(first)]);
    const fresh = findNewDecisionKeys(known, [first, second]);

    expect(fresh.has(decisionKey(second))).toBe(true);
    expect(fresh.has(decisionKey(first))).toBe(false);
  });

  it("returns an empty set when a poll finds no new rows", () => {
    const known = new Set([decisionKey(first), decisionKey(second)]);
    expect(findNewDecisionKeys(known, [first, second]).size).toBe(0);
  });

  it("handles an empty poll result against a known set", () => {
    const known = new Set([decisionKey(first)]);
    expect(findNewDecisionKeys(known, []).size).toBe(0);
  });
});

describe("formatDecisionTime", () => {
  it("formats an ISO timestamp as HH:MM:SS UTC", () => {
    expect(formatDecisionTime("2026-07-17T10:03:07Z")).toBe("10:03:07");
    expect(formatDecisionTime("2026-07-17T23:59:59.123Z")).toBe("23:59:59");
  });

  it("renders an em dash for unparseable input", () => {
    expect(formatDecisionTime("not-a-date")).toBe("—");
    expect(formatDecisionTime("")).toBe("—");
  });
});

describe("clampMetric", () => {
  it("clamps into range and passes through in-range values", () => {
    expect(clampMetric(0.5, 0, 1)).toBe(0.5);
    expect(clampMetric(1.7, 0, 1)).toBe(1);
    expect(clampMetric(-0.2, 0, 1)).toBe(0);
  });

  it("uses the fallback for non-finite input", () => {
    expect(clampMetric(Number.NaN, 0, 1, 0.5)).toBe(0.5);
    expect(clampMetric(Number.POSITIVE_INFINITY, 0, 1, 0.5)).toBe(0.5);
    expect(clampMetric(undefined, -1, 1, 0)).toBe(0);
    expect(clampMetric(null, -1, 1, 0)).toBe(0);
  });
});
