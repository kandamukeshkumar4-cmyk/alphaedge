"""L3 trade-path locustfile: authed paper buy → close cycle.

Honors rate limits with modest pacing. Zero 5xx expected.
429 onset is measured separately by run_trade_path.py probe.
"""

from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, task

from scenarios.common import (
    CANONICAL_SLUG,
    assert_local_host,
    auth_headers,
    default_host,
    unique_email,
)


class TradePathUser(HttpUser):
    """Modest paper trade cycle: buy 1 share YES → close position."""

    # Keep aggregate under global 600/min and mutating 600/min per path.
    wait_time = between(2.0, 4.0)
    host = default_host()

    def on_start(self) -> None:
        assert_local_host(self.host or default_host())
        self.slug = os.environ.get("LOADTEST_SLUG", CANONICAL_SLUG)
        self.token: str | None = None
        self.open_shares = 0.0
        email = unique_email("trade")
        password = "LoadTest20!"
        with self.client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password},
            name="POST /api/v1/auth/signup (setup)",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                try:
                    self.token = resp.json().get("access_token")
                    resp.success()
                except Exception:
                    resp.failure("signup json")
            else:
                resp.failure(f"signup {resp.status_code}")

    def _headers(self) -> dict[str, str]:
        assert self.token
        h = auth_headers(self.token)
        h["Idempotency-Key"] = uuid.uuid4().hex[:32]
        return h

    @task(3)
    def buy_yes(self) -> None:
        if not self.token:
            return
        body = {
            "slug": self.slug,
            "side": "buy",
            "outcome": "yes",
            "shares": 1,
            "price": 0.5,
        }
        with self.client.post(
            "/api/v1/orders",
            json=body,
            headers=self._headers(),
            name="POST /api/v1/orders (buy)",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx {resp.status_code}")
                return
            if resp.status_code == 429:
                resp.failure("429 rate limited")
                return
            if resp.status_code in (200, 201):
                self.open_shares += 1.0
                resp.success()
                return
            # 400 insufficient / 409 price/lock — not 5xx; record as failure for rate
            resp.failure(f"status={resp.status_code}")

    @task(2)
    def close_position(self) -> None:
        if not self.token or self.open_shares < 1:
            return
        body = {
            "slug": self.slug,
            "outcome": "yes",
            "shares": 1,
            "price": 0.5,
        }
        with self.client.post(
            "/api/v1/positions/close",
            json=body,
            headers=self._headers(),
            name="POST /api/v1/positions/close",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx {resp.status_code}")
                return
            if resp.status_code == 429:
                resp.failure("429 rate limited")
                return
            if resp.status_code == 200:
                self.open_shares = max(0.0, self.open_shares - 1.0)
                resp.success()
                return
            resp.failure(f"status={resp.status_code}")

    @task(1)
    def portfolio_check(self) -> None:
        if not self.token:
            return
        with self.client.get(
            "/api/v1/portfolio",
            headers=auth_headers(self.token),
            name="GET /api/v1/portfolio (trade cycle)",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"5xx {resp.status_code}")
            elif resp.status_code == 429:
                resp.failure("429 rate limited")
            elif resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"status={resp.status_code}")
