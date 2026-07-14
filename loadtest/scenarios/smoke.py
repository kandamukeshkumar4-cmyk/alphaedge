"""L1 smoke locustfile: /health + /api/v1/markets only.

Run via loadtest/scripts/run_smoke.py (enforces local host + records stats).
"""

from __future__ import annotations

from locust import HttpUser, between, task

from scenarios.common import assert_local_host, default_host


class SmokeUser(HttpUser):
    """20 VUs × 60s smoke against local stack only.

    wait_time is deliberately modest: the global slowapi default is
    RATE_LIMIT=600/minute per IP. Aggressive waits (0.1–0.5s) with 20 VUs
    reliably trip 429 on /api/v1/markets (~40 rps). Smoke validates the
    harness + happy path; L3 documents 429 onset on the mutating path.
    """

    wait_time = between(2.0, 3.5)
    host = default_host()

    def on_start(self) -> None:
        assert_local_host(self.host or default_host())

    @task(3)
    def health(self) -> None:
        with self.client.get("/health", name="GET /health", catch_response=True) as resp:
            if resp.status_code == 429:
                # Count rate-limit separately so harness stays honest.
                resp.failure("429 rate limited (global RATE_LIMIT)")
                return
            if resp.status_code != 200:
                resp.failure(f"status={resp.status_code}")
            else:
                try:
                    body = resp.json()
                except Exception:
                    resp.failure("invalid json")
                    return
                if body.get("paper_trading_only") is not True:
                    resp.failure("paper_trading_only missing/false")
                else:
                    resp.success()

    @task(7)
    def markets(self) -> None:
        with self.client.get(
            "/api/v1/markets", name="GET /api/v1/markets", catch_response=True
        ) as resp:
            if resp.status_code == 429:
                resp.failure("429 rate limited (global RATE_LIMIT)")
                return
            if resp.status_code != 200:
                resp.failure(f"status={resp.status_code}")
                return
            try:
                data = resp.json()
            except Exception:
                resp.failure("invalid json")
                return
            if not isinstance(data, list):
                resp.failure(f"expected list, got {type(data).__name__}")
                return
            resp.success()
