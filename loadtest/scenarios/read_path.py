"""L2 read-path locustfile.

Endpoints (GOAL L2):
  markets list (default + sort=active), market detail, candles,
  signals/events, leaderboard, portfolio (authed), feed.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task

from scenarios.common import (
    CANONICAL_SLUG,
    assert_local_host,
    auth_headers,
    default_host,
    unique_email,
)


def _ok_or_empty(status: int) -> bool:
    """200 is success; 404 on empty seeded slices is acceptable for baseline."""
    return status in (200, 404)


class ReadPathUser(HttpUser):
    """Mixed read traffic against local stack."""

    wait_time = between(1.5, 3.0)
    host = default_host()

    def on_start(self) -> None:
        assert_local_host(self.host or default_host())
        self.slug = os.environ.get("LOADTEST_SLUG", CANONICAL_SLUG)
        self.token: str | None = None
        # One paper user per VU for portfolio auth.
        email = unique_email("read")
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
            elif resp.status_code == 429:
                resp.failure("signup 429")
            else:
                resp.failure(f"signup {resp.status_code}")

    def _get(self, path: str, name: str, headers: dict | None = None) -> None:
        with self.client.get(
            path, name=name, headers=headers, catch_response=True
        ) as resp:
            if resp.status_code == 429:
                resp.failure("429 rate limited")
                return
            if resp.status_code >= 500:
                resp.failure(f"5xx {resp.status_code}")
                return
            if not _ok_or_empty(resp.status_code):
                resp.failure(f"status={resp.status_code}")
                return
            resp.success()

    @task(4)
    def markets_default(self) -> None:
        self._get("/api/v1/markets", "GET /api/v1/markets")

    @task(3)
    def markets_sort_active(self) -> None:
        self._get("/api/v1/markets?sort=active", "GET /api/v1/markets?sort=active")

    @task(3)
    def market_detail(self) -> None:
        self._get(
            f"/api/v1/markets/{self.slug}/detail",
            "GET /api/v1/markets/{slug}/detail",
        )

    @task(2)
    def market_by_slug(self) -> None:
        self._get(
            f"/api/v1/markets/{self.slug}",
            "GET /api/v1/markets/{slug}",
        )

    @task(3)
    def candles(self) -> None:
        self._get(
            f"/api/v1/markets/{self.slug}/candles",
            "GET /api/v1/markets/{slug}/candles",
        )

    @task(2)
    def signals(self) -> None:
        self._get("/api/v1/signals", "GET /api/v1/signals")

    @task(2)
    def signals_feed(self) -> None:
        self._get("/api/v1/signals/feed", "GET /api/v1/signals/feed")

    @task(2)
    def leaderboard(self) -> None:
        self._get("/api/v1/leaderboard", "GET /api/v1/leaderboard")

    @task(2)
    def feed(self) -> None:
        self._get("/api/v1/feed", "GET /api/v1/feed")

    @task(2)
    def portfolio(self) -> None:
        if not self.token:
            return
        self._get(
            "/api/v1/portfolio",
            "GET /api/v1/portfolio (authed)",
            headers=auth_headers(self.token),
        )

    @task(1)
    def portfolio_summary(self) -> None:
        if not self.token:
            return
        self._get(
            "/api/v1/portfolio/summary",
            "GET /api/v1/portfolio/summary (authed)",
            headers=auth_headers(self.token),
        )
