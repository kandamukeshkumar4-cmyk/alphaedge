"""One-shot verifier for docs/api.md path claims. Not part of product."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
doc = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
snap = set(json.loads((ROOT / "backend/tests/fixtures/openapi_snapshot.json").read_text()))

# Paths in markdown tables (backtick-wrapped absolute API paths)
table_paths: set[str] = set()
for line in doc.splitlines():
    if "|" not in line:
        continue
    for p in re.findall(r"`(/[a-zA-Z0-9_\-{}/.]+)`", line):
        if p.startswith(("/api/", "/admin", "/health", "/metrics")) and not p.endswith(
            (".py", ".json")
        ):
            table_paths.add(p.split("?")[0])

# Build code path set from routers
code_paths: set[str] = {"/", "/health", "/metrics"}
for py in (ROOT / "backend" / "app").rglob("*.py"):
    text = py.read_text(encoding="utf-8", errors="replace")
    prefixes = re.findall(r'APIRouter\(\s*prefix="([^"]+)"', text)
    prefixes += re.findall(r"APIRouter\(\s*prefix='([^']+)'", text)
    if not prefixes:
        # leaderboard router has no prefix; mounted under /api/v1 via include
        if py.name == "leaderboard.py":
            prefixes = [""]
        else:
            prefixes = [""]
    routes = re.findall(
        r'@(?:router|sources_router|admin_router)\.(?:get|post|put|patch|delete|websocket)\(\s*["\']([^"\']+)["\']',
        text,
    )
    # multi-arg decorators where path is first positional after newline
    routes += re.findall(
        r'@(?:router|sources_router|admin_router)\.(?:get|post|put|patch|delete|websocket)\(\s*\n\s*["\']([^"\']+)["\']',
        text,
    )
    # collect alternate router prefixes (sources_router, admin_router)
    alt = re.findall(
        r'(sources_router|admin_router)\s*=\s*APIRouter\(\s*prefix="([^"]+)"',
        text,
    )
    for _name, pfx in alt:
        for path in re.findall(
            rf'@{_name}\.(?:get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']',
            text,
        ):
            full = (pfx.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/")
            code_paths.add(full)
    for pfx in prefixes:
        for path in routes:
            if pfx:
                full = pfx.rstrip("/") + "/" + path.lstrip("/")
            else:
                full = path if path.startswith("/") else "/" + path
            full = full.replace("//", "/")
            if not full.startswith("/"):
                full = "/" + full
            code_paths.add(full)

# leaderboard is included on v1 with prefix /api/v1
if "/leaderboard" in code_paths:
    code_paths.add("/api/v1/leaderboard")

# admin agent router prefix /admin/agents
for py in (ROOT / "backend" / "app" / "admin").rglob("*.py"):
    text = py.read_text(encoding="utf-8", errors="replace")
    prefixes = re.findall(r'APIRouter\(\s*prefix="([^"]+)"', text)
    routes = re.findall(
        r'@router\.(?:get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']',
        text,
    )
    for pfx in prefixes:
        for path in routes:
            full = (pfx.rstrip("/") + "/" + path.lstrip("/")).replace("//", "/")
            code_paths.add(full)

# Also main.py app-level routes
main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
for path in re.findall(r'@app\.(?:get|post)\(\s*["\']([^"\']+)["\']', main):
    code_paths.add(path)

# Explicit code-verified routes using non-`router` names (sources_router in sports.py)
code_paths.add("/api/v1/system/sources")

missing = sorted(p for p in table_paths if p not in snap and p not in code_paths)
print(f"table_paths={len(table_paths)} snap={len(snap)} code={len(code_paths)}")
print("MISSING:")
for m in missing:
    print(" ", m)
print("PASS" if not missing else f"FAIL {len(missing)}")
