const { app } = require("@azure/functions");
const {
  proxyAdminAgentRun,
  proxyAdminAgentRunDetail,
  proxyAdminAgentRuns,
  proxyAdminMarketSnapshotCaptures,
} = require("../admin-proxy");

const DISCLAIMER =
  "This project is a paper-trading simulation for research and portfolio demonstration only. No real-money trading, betting, or settlement is supported.";

const canonicalMarket = {
  id: "11111111-1111-1111-1111-111111111111",
  slug: "nba-2025-01-15-lal-bos",
  title: "Lakers vs Celtics",
  question: "Will the Lakers win?",
  status: "open",
  lock_at: "2025-01-15T19:30:00Z",
  resolved_at: null,
  winning_outcome: null,
};

app.http("health", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "health",
  handler: async () => ({
    jsonBody: {
      status: "ok",
      paper_trading_only: true,
      disclaimer: DISCLAIMER,
      runtime: "azure-static-web-apps-managed-api",
    },
  }),
});

app.http("markets", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "v1/markets",
  handler: async () => ({
    jsonBody: [canonicalMarket],
  }),
});

app.http("marketBySlug", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "v1/markets/{slug}",
  handler: async (request) => {
    if (request.params.slug !== canonicalMarket.slug) {
      return {
        status: 404,
        jsonBody: { detail: "Market not found" },
      };
    }

    return { jsonBody: canonicalMarket };
  },
});

app.http("evalAggregates", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "v1/eval/aggregates",
  handler: async () => ({
    jsonBody: {
      window_days: 7,
      mean_brier: 0.2148,
      calibration_error: 0.0385,
      market_count: 250,
    },
  }),
});

app.http("adminAgentRuns", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "proof/agents/runs",
  handler: proxyAdminAgentRuns,
});

app.http("adminAgentRun", {
  methods: ["POST"],
  authLevel: "anonymous",
  route: "proof/agents/run/{slug}",
  handler: proxyAdminAgentRun,
});

app.http("adminAgentRunDetail", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "proof/agents/runs/{runId}",
  handler: proxyAdminAgentRunDetail,
});

app.http("adminMarketSnapshotCaptures", {
  methods: ["GET"],
  authLevel: "anonymous",
  route: "proof/market-snapshot-captures",
  handler: proxyAdminMarketSnapshotCaptures,
});
