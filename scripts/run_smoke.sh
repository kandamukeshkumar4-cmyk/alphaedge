#!/usr/bin/env bash
# Run the E2E user-journey smoke suite against a running AlphaEdge deployment.
#
#   ./scripts/run_smoke.sh                                  # local stack
#   ./scripts/run_smoke.sh https://mukeshkumarkanda-alphaedge-api.hf.space
#   ALPHAEDGE_EXPECT_LLM=1 ./scripts/run_smoke.sh <url>     # fail if AI is in fallback mode
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://127.0.0.1:8000}}"
cd "$(dirname "$0")/../backend"

echo "Running E2E smoke suite against ${BASE_URL}"
uv run --extra dev pytest tests/smoke/ -q --base-url "${BASE_URL}"
