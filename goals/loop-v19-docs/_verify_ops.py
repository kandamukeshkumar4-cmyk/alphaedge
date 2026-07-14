"""Verify docs/operations.md env names and endpoints."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
doc = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
cfg = (ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")
envex = (ROOT / ".env.example").read_text(encoding="utf-8")
snap = set(json.loads((ROOT / "backend/tests/fixtures/openapi_snapshot.json").read_text()))

aliases = set(re.findall(r'alias="([A-Z][A-Z0-9_]+)"', cfg))
env_names = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", envex, re.M))
known = aliases | env_names | {
    "BASE_URL",
    "FRONTEND_URL",
    "PORT",
    "RAILWAY_TOKEN",
    "NEON_DATABASE_URL",
    "NEON_DATABASE_URL_SYNC",
    "NEXT_PUBLIC_API_URL",
}
vars_ = sorted(set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", doc)))
missing_env = [v for v in vars_ if v not in known]
print("env tokens", len(vars_))
print("missing env", missing_env or "NONE")

apis = sorted(set(re.findall(r"(/api/v1/[a-zA-Z0-9_\-/*{}]+|/metrics|/health)", doc)))
code_extra = {
    "/api/v1/system/sources",
    "/api/v1/system/loops",
    "/api/v1/system/metrics",
    "/api/v1/system/resolved-count",
    "/api/v1/system/model-ab",
    "/metrics",
    "/health",
}
miss_api = []
for a in apis:
    if a.endswith("/*"):
        prefix = a[:-1]
        if any(s.startswith(prefix) for s in snap):
            continue
        miss_api.append(a)
        continue
    if a in snap or a in code_extra:
        continue
    miss_api.append(a)
print("apis", apis)
print("missing apis", miss_api or "NONE")

files = [
    "backend/railway.toml",
    "backend/railway.worker.toml",
    "scripts/deploy_railway.ps1",
    ".github/workflows/demo-uptime.yml",
    "scripts/verify_prod.py",
    "backend/app/core/config.py",
    "backend/alembic/versions/018_wc2026_tag.py",
    "backend/alembic/versions/040_portfolio_equity_snapshots.py",
]
for rel in files:
    print(("OK" if (ROOT / rel).exists() else "MISS"), rel)

print("PASS" if not missing_env and not miss_api else "FAIL")
