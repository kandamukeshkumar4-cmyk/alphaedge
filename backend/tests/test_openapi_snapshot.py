"""Loop V15 E4 — OpenAPI contract snapshot.

Locks the public API surface (paths, methods, operation summaries, tags, and
success-response presence) against ACCIDENTAL breaking changes:

* Removing a path/method that exists in the snapshot fails.
* Changing an operation's summary/tags fails (docs are part of the contract).
* ADDING new paths/methods is allowed (additive API is this repo's rule) —
  regenerate the snapshot alongside the intentional change:

      cd backend && uv run python scripts/regen_openapi_snapshot.py

Deliberately NOT byte-for-byte on the whole document: schema component
internals may evolve as long as the operation surface stays stable.

Also asserts baseline doc quality: every operation has a non-empty summary
and at least one tag.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"
METHODS = ("get", "post", "put", "patch", "delete")


def _current_surface() -> dict:
    schema = app.openapi()
    snap: dict = {}
    for path, ops in sorted(schema["paths"].items()):
        entry = {}
        for method, op in sorted(ops.items()):
            if method not in METHODS:
                continue
            entry[method] = {
                "summary": op.get("summary", ""),
                "tags": sorted(op.get("tags", [])),
                "has_success_response": any(
                    str(code).startswith("2") for code in op.get("responses", {})
                ),
            }
        if entry:
            snap[path] = entry
    return snap


def test_openapi_surface_matches_snapshot():
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    current = _current_surface()

    removed_paths = sorted(set(snapshot) - set(current))
    assert not removed_paths, f"BREAKING: paths removed from the API: {removed_paths}"

    problems: list[str] = []
    for path, methods in snapshot.items():
        for method, expected in methods.items():
            actual = current[path].get(method)
            if actual is None:
                problems.append(f"BREAKING: {method.upper()} {path} removed")
                continue
            if actual != expected:
                problems.append(
                    f"CHANGED: {method.upper()} {path}: {expected!r} -> {actual!r}"
                )
    assert not problems, "\n".join(problems)


def test_every_operation_documented():
    current = _current_surface()
    undocumented = [
        f"{method.upper()} {path}"
        for path, methods in current.items()
        for method, meta in methods.items()
        if not meta["summary"].strip() or not meta["tags"]
    ]
    assert not undocumented, f"operations missing summary or tags: {undocumented}"


def test_every_operation_declares_a_success_response():
    current = _current_surface()
    missing = [
        f"{method.upper()} {path}"
        for path, methods in current.items()
        for method, meta in methods.items()
        if not meta["has_success_response"]
    ]
    assert not missing, f"operations without a 2xx response: {missing}"
