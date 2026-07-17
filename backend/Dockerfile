FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Railway builds this Dockerfile (backend/railway.toml). The A/B harness must
# refuse unless the real LightGBM arm is importable, so include the already
# lock-pinned optional ML extra rather than falling back to XGBoost.
RUN pip install --no-cache-dir uv && uv sync --no-dev --extra ml-extra

ENV PAPER_TRADING_ONLY=true

# Migrations run via railway.toml preDeployCommand on Railway; keep alembic
# here so docker compose / one-off containers still self-bootstrap.
# Boot durably: migrations must never block the web server from answering the
# platform healthcheck. `timeout` caps a slow/locked `alembic upgrade head`
# (e.g. lock contention between overlapping deploys over the managed-PG proxy);
# uvicorn ALWAYS starts, so /health comes up. Any brief missing-table window is
# already handled by the app's DB-unavailable 503 handler (REL-COLD-DB).
CMD ["sh", "-c", "timeout 150 uv run alembic upgrade head || echo '[boot] alembic did not complete (timeout/err) — starting API anyway'; uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
