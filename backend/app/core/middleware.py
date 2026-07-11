import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.activity import is_monitoring_path, mark_activity


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        if not is_monitoring_path(request.url.path):
            mark_activity()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
