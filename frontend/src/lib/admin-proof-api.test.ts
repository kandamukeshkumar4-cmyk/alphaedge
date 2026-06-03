import { describe, expect, it, vi } from "vitest";

import { fetchAdminAgentRunDetail, fetchAdminAgentRuns } from "./admin-proof-api";

describe("admin proof API", () => {
  it("loads agent run summaries through the same-origin viewer-token proxy", async () => {
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("/api/proof/agents/runs?limit=2");
      expect(init?.headers).toEqual({
        "x-alphaedge-admin-viewer-token": "viewer-secret",
      });
      expect(JSON.stringify(init)).not.toContain("backend-secret");
      return jsonResponse({
        disclaimer: "Paper-trading simulation only.",
        runs: [
          {
            run_id: "run-1",
            market_id: "market-1",
            market_slug: "nba-2025-01-15-lal-bos",
            market_title: "Lakers vs Celtics",
            status: "blocked",
            graph_version: "v1",
            approved: false,
            step_count: 5,
            errors: ["edge 3.00% < 5%"],
            created_at: "2026-06-03T15:00:00Z",
          },
        ],
      });
    });

    const result = await fetchAdminAgentRuns({
      fetcher,
      viewerToken: "viewer-secret",
      limit: 2,
    });

    expect(result).toMatchObject({
      ok: true,
      runs: [
        {
          run_id: "run-1",
          market_slug: "nba-2025-01-15-lal-bos",
          errors: ["edge 3.00% < 5%"],
        },
      ],
    });
  });

  it("loads one detailed proof run by id", async () => {
    const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("/api/proof/agents/runs/run-1");
      expect(init?.headers).toEqual({
        "x-alphaedge-admin-viewer-token": "viewer-secret",
      });
      return jsonResponse({
        run_id: "run-1",
        market_id: "market-1",
        market_slug: "nba-2025-01-15-lal-bos",
        market_title: "Lakers vs Celtics",
        status: "blocked",
        graph_version: "v1",
        approved: false,
        predicted_prob: 0.58,
        confidence: 0.75,
        reasoning: "Risk rejected.",
        errors: ["edge 3.00% < 5%"],
        created_at: "2026-06-03T15:00:00Z",
        disclaimer: "Paper-trading simulation only.",
        steps: [
          {
            step_name: "risk",
            input_data: { predicted_prob: 0.58 },
            output_data: { approved: false, errors: ["edge 3.00% < 5%"] },
          },
        ],
      });
    });

    const result = await fetchAdminAgentRunDetail({
      fetcher,
      viewerToken: "viewer-secret",
      runId: "run-1",
    });

    expect(result).toMatchObject({
      ok: true,
      run: {
        run_id: "run-1",
        steps: [{ step_name: "risk" }],
      },
    });
  });

  it("does not call the proxy without a viewer token", async () => {
    const fetcher = vi.fn();

    const result = await fetchAdminAgentRuns({
      fetcher,
      viewerToken: " ",
    });

    expect(result).toEqual({
      ok: false,
      message: "Admin viewer token is required.",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
