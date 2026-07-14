"""Shared HTTP JSON client for external data connectors.

Resilience (Loop V15 C1):
- per-request timeout (via httpx.Client)
- bounded retry on 5xx / transport errors with full-jitter backoff
- per-source circuit breaker (skip source for cooldown after consecutive failures)
- structured logging on degradation
- in-memory response cache (unchanged)

Paper-only read path — never touches orders.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

# Defaults tuned for short connector polls (not long WS reconnects).
_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BASE_BACKOFF_SEC = 0.05
_DEFAULT_BACKOFF_CAP_SEC = 1.0
_DEFAULT_FAILURE_THRESHOLD = 3
_DEFAULT_COOLDOWN_SEC = 300.0  # 5 minutes


class CircuitOpenError(RuntimeError):
    """Raised when a connector source's circuit breaker is open."""

    def __init__(self, source: str, open_until: float):
        self.source = source
        self.open_until = open_until
        super().__init__(f"circuit open for source={source!r} until={open_until:.3f}")


@dataclass
class SourceHealth:
    """Snapshot of per-source resilience state (consumed later by C3)."""

    source: str
    consecutive_failures: int = 0
    open_until: float | None = None
    last_success_at: float | None = None
    last_error: str | None = None
    total_successes: int = 0
    total_failures: int = 0

    @property
    def state(self) -> str:
        # open_until is cleared lazily by JsonConnectorClient when cooldown elapses.
        if self.open_until is not None:
            return "open"
        if self.consecutive_failures > 0:
            return "degraded"
        return "healthy"


# Module registry so C3 can report health without holding client refs.
_SOURCE_HEALTH: dict[str, SourceHealth] = {}


def get_source_health(source: str | None = None) -> dict[str, SourceHealth] | SourceHealth | None:
    """Return one source's health, all sources, or None if unknown."""
    if source is None:
        return dict(_SOURCE_HEALTH)
    return _SOURCE_HEALTH.get(source)


def refresh_source_health(*, monotonic: Callable[[], float] = time.monotonic) -> dict[str, SourceHealth]:
    """Expire cooldowns lazily (same rule as JsonConnectorClient) and return all rows."""
    now = monotonic()
    for row in _SOURCE_HEALTH.values():
        if row.open_until is not None and now >= row.open_until:
            row.open_until = None
    return dict(_SOURCE_HEALTH)


def reset_source_health() -> None:
    """Test helper — clear the module-level health registry."""
    _SOURCE_HEALTH.clear()


def _jitter_delay(
    attempt: int,
    *,
    base_sec: float,
    cap_sec: float,
    rng: random.Random,
) -> float:
    """Full-jitter exponential backoff: uniform(0, min(cap, base * 2**attempt))."""
    ceiling = min(cap_sec, base_sec * (2**attempt))
    return rng.uniform(0.0, ceiling)


class JsonConnectorClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
        *,
        source: str = "unnamed",
        timeout: float = 10.0,
        base_backoff_sec: float = _DEFAULT_BASE_BACKOFF_SEC,
        backoff_cap_sec: float = _DEFAULT_BACKOFF_CAP_SEC,
        failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD,
        cooldown_sec: float = _DEFAULT_COOLDOWN_SEC,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self.base_url = base_url.rstrip("/")
        self.source = source
        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout)
        self.max_attempts = max(1, max_attempts)
        self.base_backoff_sec = max(0.0, base_backoff_sec)
        self.backoff_cap_sec = max(self.base_backoff_sec, backoff_cap_sec)
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_sec = max(0.0, cooldown_sec)
        self._sleep = sleep
        self._rng = rng or random.Random()
        self._monotonic = monotonic
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], Any] = {}
        self._ensure_health_row()

    def _ensure_health_row(self) -> SourceHealth:
        row = _SOURCE_HEALTH.get(self.source)
        if row is None:
            row = SourceHealth(source=self.source)
            _SOURCE_HEALTH[self.source] = row
        return row

    def health(self) -> SourceHealth:
        # Expire open circuits lazily so state() matches the injectable clock.
        self._circuit_open_until()
        return self._ensure_health_row()

    def _circuit_open_until(self) -> float | None:
        row = self._ensure_health_row()
        if row.open_until is None:
            return None
        if self._monotonic() >= row.open_until:
            # Cooldown elapsed — half-open: allow one probe.
            row.open_until = None
            return None
        return row.open_until

    def _raise_if_circuit_open(self) -> None:
        open_until = self._circuit_open_until()
        if open_until is not None:
            logger.warning(
                "connector_circuit_open",
                extra={
                    "source": self.source,
                    "open_until": open_until,
                    "event": "circuit_open_skip",
                },
            )
            raise CircuitOpenError(self.source, open_until)

    def _record_success(self) -> None:
        row = self._ensure_health_row()
        row.consecutive_failures = 0
        row.open_until = None
        row.last_success_at = self._monotonic()
        row.last_error = None
        row.total_successes += 1

    def _record_failure(self, exc: BaseException) -> None:
        row = self._ensure_health_row()
        row.consecutive_failures += 1
        row.total_failures += 1
        row.last_error = f"{type(exc).__name__}: {exc}"
        if row.consecutive_failures >= self.failure_threshold:
            row.open_until = self._monotonic() + self.cooldown_sec
            logger.warning(
                "connector_circuit_opened source=%s failures=%d cooldown_sec=%.1f error=%s",
                self.source,
                row.consecutive_failures,
                self.cooldown_sec,
                row.last_error,
            )
        else:
            logger.warning(
                "connector_degraded source=%s consecutive_failures=%d error=%s",
                self.source,
                row.consecutive_failures,
                row.last_error,
            )

    def _should_retry_status(self, status_code: int) -> bool:
        return status_code >= 500

    def _retry_sleep(self, attempt: int) -> None:
        delay = _jitter_delay(
            attempt,
            base_sec=self.base_backoff_sec,
            cap_sec=self.backoff_cap_sec,
            rng=self._rng,
        )
        if delay > 0:
            logger.info(
                "connector_retry_backoff source=%s attempt=%d delay_sec=%.4f",
                self.source,
                attempt + 1,
                delay,
            )
            self._sleep(delay)

    def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        normalized_params = tuple(sorted((params or {}).items()))
        cache_key = (path, normalized_params)
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._raise_if_circuit_open()

        last_exc: BaseException | None = None
        for attempt in range(self.max_attempts):
            try:
                response = self.client.get(path, params=params)
                if self._should_retry_status(response.status_code) and attempt < self.max_attempts - 1:
                    logger.warning(
                        "connector_upstream_5xx source=%s status=%d attempt=%d/%d",
                        self.source,
                        response.status_code,
                        attempt + 1,
                        self.max_attempts,
                    )
                    self._retry_sleep(attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                self._cache[cache_key] = payload
                self._record_success()
                return payload
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.TransportError)) or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and self._should_retry_status(exc.response.status_code)
                )
                if retryable and attempt < self.max_attempts - 1:
                    logger.warning(
                        "connector_retry source=%s attempt=%d/%d error=%s",
                        self.source,
                        attempt + 1,
                        self.max_attempts,
                        f"{type(exc).__name__}: {exc}",
                    )
                    self._retry_sleep(attempt)
                    continue
                # 4xx is a caller/config error — do not trip the circuit.
                if isinstance(exc, httpx.HTTPStatusError) and not self._should_retry_status(
                    exc.response.status_code
                ):
                    raise
                break

        assert last_exc is not None
        self._record_failure(last_exc)
        raise last_exc

    def post_json(self, path: str, json: Any | None = None) -> Any:
        """POST JSON with the same timeout/retry/circuit-breaker path as GET."""
        self._raise_if_circuit_open()

        last_exc: BaseException | None = None
        for attempt in range(self.max_attempts):
            try:
                response = self.client.post(path, json=json)
                if self._should_retry_status(response.status_code) and attempt < self.max_attempts - 1:
                    logger.warning(
                        "connector_upstream_5xx source=%s status=%d attempt=%d/%d method=POST",
                        self.source,
                        response.status_code,
                        attempt + 1,
                        self.max_attempts,
                    )
                    self._retry_sleep(attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                self._record_success()
                return payload
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.TransportError)) or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and self._should_retry_status(exc.response.status_code)
                )
                if retryable and attempt < self.max_attempts - 1:
                    self._retry_sleep(attempt)
                    continue
                if isinstance(exc, httpx.HTTPStatusError) and not self._should_retry_status(
                    exc.response.status_code
                ):
                    raise
                break

        assert last_exc is not None
        self._record_failure(last_exc)
        raise last_exc
