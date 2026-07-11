import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.activity import is_monitoring_path, mark_activity
from app.observability import http_metrics


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        if not is_monitoring_path(request.url.path):
            mark_activity()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def _route_key(request: Request) -> str:
    """Templated path for the matched route (bounds the metrics key space).

    Falls back to a coarse bucket when no route matched (404s / unmounted
    paths) so path params can never explode the in-memory map.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "__unmatched__"


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    """Lightweight per-route timing/counter middleware (Loop V13 R01).

    Records request count, error count (5xx), and latency samples into the
    in-process ``http_metrics`` registry. An unhandled exception is counted as
    a 500 and then re-raised so the normal error path is unchanged.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            http_metrics.record_request(
                method=request.method,
                route=_route_key(request),
                status_code=status_code,
                latency_ms=latency_ms,
            )
