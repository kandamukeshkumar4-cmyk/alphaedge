from __future__ import annotations

from typing import Any

import httpx


class JsonConnectorClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        max_attempts: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self.max_attempts = max(1, max_attempts)
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], Any] = {}

    def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        normalized_params = tuple(sorted((params or {}).items()))
        cache_key = (path, normalized_params)
        if cache_key in self._cache:
            return self._cache[cache_key]

        response: httpx.Response | None = None
        for attempt in range(self.max_attempts):
            response = self.client.get(path, params=params)
            if response.status_code < 500 or attempt == self.max_attempts - 1:
                response.raise_for_status()
                payload = response.json()
                self._cache[cache_key] = payload
                return payload

        raise RuntimeError("unreachable connector retry state")
