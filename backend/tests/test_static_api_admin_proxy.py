import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_static_api_admin_agent_runs_proxy_requires_viewer_token_and_forwards_server_key():
    script = textwrap.dedent(
        """
        (async () => {
          const assert = require("node:assert/strict");
          const { proxyAdminAgentRuns } = require("./api/src/admin-proxy");

          const calls = [];
          const response = await proxyAdminAgentRuns(
            {
              query: new URLSearchParams("limit=2"),
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test/",
              },
              fetchImpl: async (url, init) => {
                calls.push({ url, init });
                return {
                  status: 200,
                  async json() {
                    return { runs: [{ run_id: "run-1" }] };
                  },
                };
              },
            },
          );

          assert.equal(response.status, 200);
          assert.deepEqual(response.jsonBody, { runs: [{ run_id: "run-1" }] });
          assert.equal(calls.length, 1);
          assert.equal(calls[0].url, "https://api.example.test/admin/agents/runs?limit=2");
          assert.equal(calls[0].init.headers["X-Admin-API-Key"], "backend-secret");

          const missingViewerToken = await proxyAdminAgentRuns(
            {
              query: new URLSearchParams("limit=2"),
              headers: new Map(),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test",
              },
              fetchImpl: async () => {
                throw new Error("fetch must not run without viewer token");
              },
            },
          );
          assert.equal(missingViewerToken.status, 401);
          assert.deepEqual(missingViewerToken.jsonBody, { detail: "Invalid admin viewer token" });

          const unconfigured = await proxyAdminAgentRuns(
            {
              query: new URLSearchParams(),
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test",
              },
            },
          );
          assert.equal(unconfigured.status, 503);
          assert.deepEqual(unconfigured.jsonBody, { detail: "Admin proof proxy not configured" });
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_static_api_admin_capture_health_proxy_forwards_query_without_exposing_key():
    script = textwrap.dedent(
        """
        (async () => {
          const assert = require("node:assert/strict");
          const { proxyAdminMarketSnapshotCaptures } = require("./api/src/admin-proxy");

          const calls = [];
          const response = await proxyAdminMarketSnapshotCaptures(
            {
              query: new URLSearchParams("limit=3"),
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test/",
              },
              fetchImpl: async (url, init) => {
                calls.push({ url, init });
                return {
                  status: 200,
                  async json() {
                    return {
                      runs: [
                        {
                          run_id: "capture-run-1",
                          status: "degraded",
                          fetched: 3,
                          ingested: 2,
                          skipped: 1,
                          failed: 1,
                          failures: [
                            {
                              source: "kalshi.rest",
                              target: "KXNBA-LALBOS-26JAN15",
                              error: "upstream 500",
                            },
                          ],
                          started_at: "2026-01-14T18:00:00Z",
                          finished_at: "2026-01-14T18:01:00Z",
                          captured_at: "2026-01-14T18:00:00Z",
                        },
                      ],
                    };
                  },
                };
              },
            },
          );

          assert.equal(response.status, 200);
          assert.equal(response.jsonBody.runs[0].status, "degraded");
          assert.equal(calls.length, 1);
          assert.equal(
            calls[0].url,
            "https://api.example.test/admin/market-snapshot-captures?limit=3",
          );
          assert.equal(calls[0].init.headers["X-Admin-API-Key"], "backend-secret");
          assert.ok(!JSON.stringify(response).includes("backend-secret"));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_static_api_admin_historical_capture_proxy_forwards_query_without_exposing_key():
    script = textwrap.dedent(
        """
        (async () => {
          const assert = require("node:assert/strict");
          const {
            proxyAdminHistoricalClosingSnapshotCaptures,
          } = require("./api/src/admin-proxy");

          const calls = [];
          const response = await proxyAdminHistoricalClosingSnapshotCaptures(
            {
              query: new URLSearchParams("limit=3"),
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test/",
              },
              fetchImpl: async (url, init) => {
                calls.push({ url, init });
                return {
                  status: 200,
                  async json() {
                    return { runs: [{ run_id: "historical-run-1", status: "success" }] };
                  },
                };
              },
            },
          );

          assert.equal(response.status, 200);
          assert.equal(response.jsonBody.runs[0].run_id, "historical-run-1");
          assert.equal(calls.length, 1);
          assert.equal(
            calls[0].url,
            "https://api.example.test/admin/historical-closing-snapshot-captures?limit=3",
          );
          assert.equal(calls[0].init.headers["X-Admin-API-Key"], "backend-secret");
          assert.ok(!JSON.stringify(response).includes("backend-secret"));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_static_api_admin_historical_capture_proxy_posts_without_exposing_key():
    script = textwrap.dedent(
        """
        (async () => {
          const assert = require("node:assert/strict");
          const {
            proxyAdminHistoricalClosingSnapshotCaptureRun,
          } = require("./api/src/admin-proxy");

          const calls = [];
          const response = await proxyAdminHistoricalClosingSnapshotCaptureRun(
            {
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test",
              },
              fetchImpl: async (url, init) => {
                calls.push({ url, init });
                return {
                  status: 200,
                  async json() {
                    return { run_id: "historical-run-1", status: "success" };
                  },
                };
              },
            },
          );

          assert.equal(response.status, 200);
          assert.deepEqual(response.jsonBody, {
            run_id: "historical-run-1",
            status: "success",
          });
          assert.equal(calls.length, 1);
          assert.equal(
            calls[0].url,
            "https://api.example.test/admin/historical-closing-snapshot-captures",
          );
          assert.equal(calls[0].init.method, "POST");
          assert.equal(calls[0].init.headers["X-Admin-API-Key"], "backend-secret");
          assert.ok(!JSON.stringify(response).includes("backend-secret"));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_static_api_admin_agent_run_detail_proxy_forwards_run_id_without_exposing_key():
    script = textwrap.dedent(
        """
        (async () => {
          const assert = require("node:assert/strict");
          const { proxyAdminAgentRunDetail } = require("./api/src/admin-proxy");

          const calls = [];
          const response = await proxyAdminAgentRunDetail(
            {
              params: { runId: "11111111-1111-1111-1111-111111111111" },
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test",
              },
              fetchImpl: async (url, init) => {
                calls.push({ url, init });
                return {
                  status: 404,
                  async json() {
                    return { detail: "Agent run not found" };
                  },
                };
              },
            },
          );

          assert.equal(response.status, 404);
          assert.deepEqual(response.jsonBody, { detail: "Agent run not found" });
          assert.equal(
            calls[0].url,
            "https://api.example.test/admin/agents/runs/11111111-1111-1111-1111-111111111111",
          );
          assert.equal(calls[0].init.headers["X-Admin-API-Key"], "backend-secret");
          assert.ok(!JSON.stringify(response).includes("backend-secret"));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_static_api_admin_agent_run_proxy_posts_slug_without_exposing_key():
    script = textwrap.dedent(
        """
        (async () => {
          const assert = require("node:assert/strict");
          const { proxyAdminAgentRun } = require("./api/src/admin-proxy");

          const calls = [];
          const response = await proxyAdminAgentRun(
            {
              params: { slug: "nba-2025-01-15-lal-bos" },
              headers: new Map([["x-alphaedge-admin-viewer-token", "viewer-secret"]]),
            },
            {
              env: {
                ADMIN_VIEWER_TOKEN: "viewer-secret",
                ADMIN_API_KEY: "backend-secret",
                ALPHAEDGE_BACKEND_API_URL: "https://api.example.test",
              },
              fetchImpl: async (url, init) => {
                calls.push({ url, init });
                return {
                  status: 200,
                  async json() {
                    return {
                      run_id: "run-1",
                      market_slug: "nba-2025-01-15-lal-bos",
                      approved: false,
                    };
                  },
                };
              },
            },
          );

          assert.equal(response.status, 200);
          assert.deepEqual(response.jsonBody, {
            run_id: "run-1",
            market_slug: "nba-2025-01-15-lal-bos",
            approved: false,
          });
          assert.equal(calls.length, 1);
          assert.equal(
            calls[0].url,
            "https://api.example.test/admin/agents/run/nba-2025-01-15-lal-bos",
          );
          assert.equal(calls[0].init.method, "POST");
          assert.equal(calls[0].init.headers["X-Admin-API-Key"], "backend-secret");
          assert.ok(!JSON.stringify(response).includes("backend-secret"));
        })().catch((error) => {
          console.error(error);
          process.exit(1);
        });
        """
    )

    result = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
