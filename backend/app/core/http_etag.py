"""M03 — weak-ETag + conditional-GET (304) helper for heavy public GETs.

Additive HTTP-caching for the free-tier Space: a stable **weak** ETag computed
from the serialized response body, plus ``If-None-Match`` handling that returns a
bodiless **304 Not Modified** when the client already holds the current version.

Purely additive: on a normal 200 the JSON body is UNCHANGED — only an ``ETag``
response header is added. A matching ``If-None-Match`` yields 304 with an empty
body and the same ``ETag`` header. Different data hashes to a different ETag.

Used by ``/api/v1/home``, ``/api/v1/markets/{slug}/share-snapshot`` and
``/api/v1/backtest/summary``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

# Keys excluded from the ETag hash (recursively) because they are derived from
# the request-time server clock or the cache-hit flag, NOT from the meaningful
# content: ``generated_at`` (build timestamp), ``since`` (digest window start =
# now − window), ``cached`` (cache-hit flag). Including any of them would change
# the validator on every call and defeat conditional GETs. Content-bearing
# timestamps (DB ``created_at`` / ``last_signal_at`` / ``scored_at`` /
# ``last_updated``) are NOT excluded — a real data change must move the ETag.
_VOLATILE_KEYS = frozenset({"generated_at", "since", "cached"})


def _strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _strip_volatile(v)
            for k, v in value.items()
            if k not in _VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_strip_volatile(v) for v in value]
    return value


def compute_weak_etag(body: Any) -> str:
    """Stable weak ETag for a JSON-serializable body. Key ordering is normalized
    so logically-equal bodies always hash identically; clock-derived keys
    (``generated_at``, ``since``, ``cached``) are stripped recursively so the
    validator tracks content, not the wall clock."""
    payload = _strip_volatile(jsonable_encoder(body))
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:32]
    return f'W/"{digest}"'


def _client_tags(if_none_match: str | None) -> list[str]:
    if not if_none_match:
        return []
    return [tag.strip() for tag in if_none_match.split(",") if tag.strip()]


def etag_json_response(request: Request, body: Any) -> Response:
    """Return a 304 (empty body, ETag header) when the caller's ``If-None-Match``
    matches; otherwise a normal ``JSONResponse`` for ``body`` with the ``ETag``
    header added. The 200 body is byte-identical to returning ``body`` directly."""
    etag = compute_weak_etag(body)
    if etag in _client_tags(request.headers.get("if-none-match")):
        return Response(status_code=304, headers={"ETag": etag})
    payload = jsonable_encoder(body)
    return JSONResponse(content=payload, headers={"ETag": etag})
