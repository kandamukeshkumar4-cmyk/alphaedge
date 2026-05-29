#!/usr/bin/env python3
"""Seed canonical Lakers vs Celtics market via admin API."""

import os
import sys
from datetime import datetime, timezone

import httpx

API = os.getenv("API_URL", "http://localhost:8000")
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-key")

LAKERS_MARKET = {
    "slug": "nba-2025-01-15-lal-bos",
    "title": "Lakers vs Celtics",
    "question": "Will the Lakers win?",
    "lock_at": datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc).isoformat(),
}


def main() -> None:
    headers = {"X-Admin-API-Key": ADMIN_KEY}
    r = httpx.post(f"{API}/admin/markets", json=LAKERS_MARKET, headers=headers, timeout=30)
    r.raise_for_status()
    print("Seeded:", r.json())


if __name__ == "__main__":
    main()
