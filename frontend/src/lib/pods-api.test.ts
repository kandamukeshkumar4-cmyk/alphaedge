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
  formatSignedPct,
  formatVenueGap,
  formatVolumePct,
  newsSignalTone,
  normalizePodStatus,
  sortDecisionsNewestFirst,
  whalePressurePct,
  whalePressureTier,
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

// ---------------------------------------------------------------------------
// U4 — market context panel view helpers
// ---------------------------------------------------------------------------

describe("whalePressureTier", () => {
  it("buckets the 0..1 share into quiet / building / heavy", () => {
    expect(whalePressureTier(0)).toBe("quiet");
    expect(whalePressureTier(0.33)).toBe("quiet");
    expect(whalePressureTier(0.34)).toBe("building");
    expect(whalePressureTier(0.66)).toBe("building");
    expect(whalePressureTier(0.67)).toBe("heavy");
    expect(whalePressureTier(1)).toBe("heavy");
  });

  it("treats out-of-range and non-finite input defensively", () => {
    expect(whalePressureTier(1.7)).toBe("heavy");
    expect(whalePressureTier(-0.5)).toBe("quiet");
    expect(whalePressureTier(Number.NaN)).toBe("quiet");
    expect(whalePressureTier(undefined)).toBe("quiet");
    expect(whalePressureTier(null)).toBe("quiet");
  });
});

describe("whalePressurePct", () => {
  it("converts the share to a 0-100 gauge fill", () => {
    expect(whalePressurePct(0.72)).toBe(72);
    expect(whalePressurePct(0)).toBe(0);
    expect(whalePressurePct(1)).toBe(100);
  });

  it("clamps outliers and falls back to 0 for non-finite input", () => {
    expect(whalePressurePct(1.7)).toBe(100);
    expect(whalePressurePct(-0.5)).toBe(0);
    expect(whalePressurePct(Number.NaN)).toBe(0);
    expect(whalePressurePct(undefined)).toBe(0);
  });
});

describe("newsSignalTone", () => {
  it("buckets the -1..1 score around the neutral band", () => {
    expect(newsSignalTone(0.4)).toBe("positive");
    expect(newsSignalTone(0.21)).toBe("positive");
    expect(newsSignalTone(0.2)).toBe("neutral");
    expect(newsSignalTone(-0.2)).toBe("neutral");
    expect(newsSignalTone(-0.21)).toBe("negative");
    expect(newsSignalTone(-0.9)).toBe("negative");
  });

  it("clamps outliers and treats non-finite input as neutral", () => {
    expect(newsSignalTone(3)).toBe("positive");
    expect(newsSignalTone(-3)).toBe("negative");
    expect(newsSignalTone(Number.NaN)).toBe("neutral");
    expect(newsSignalTone(undefined)).toBe("neutral");
    expect(newsSignalTone(null)).toBe("neutral");
  });
});

describe("formatVenueGap", () => {
  it("renders the signed gap in cents", () => {
    expect(formatVenueGap(0.015)).toBe("+1.5¢");
    expect(formatVenueGap(-0.02)).toBe("-2.0¢");
    expect(formatVenueGap(0)).toBe("0.0¢");
    expect(formatVenueGap(0.004)).toBe("+0.4¢");
  });

  it("renders an em dash for non-finite input", () => {
    expect(formatVenueGap(Number.NaN)).toBe("—");
    expect(formatVenueGap(undefined)).toBe("—");
    expect(formatVenueGap(null)).toBe("—");
  });
});

describe("formatSignedPct", () => {
  it("renders a signed percent for the price trend", () => {
    expect(formatSignedPct(0.06)).toBe("+6.0%");
    expect(formatSignedPct(-0.025)).toBe("-2.5%");
    expect(formatSignedPct(0)).toBe("0.0%");
  });

  it("renders an em dash for non-finite input", () => {
    expect(formatSignedPct(Number.NaN)).toBe("—");
    expect(formatSignedPct(undefined)).toBe("—");
  });
});

describe("formatVolumePct", () => {
  it("renders the volume share as a whole percent", () => {
    expect(formatVolumePct(0.81)).toBe("81%");
    expect(formatVolumePct(1.24)).toBe("124%");
    expect(formatVolumePct(0)).toBe("0%");
  });

  it("never goes negative and renders an em dash for non-finite input", () => {
    expect(formatVolumePct(-0.4)).toBe("0%");
    expect(formatVolumePct(Number.NaN)).toBe("—");
    expect(formatVolumePct(undefined)).toBe("—");
  });
});
