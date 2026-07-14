# AlphaEdge backend

FastAPI paper-trading API, CLOB, workers, and ML evaluation stack.

> **`PAPER_TRADING_ONLY=true` is required.** Simulated funds only.

## Quick commands

```bash
# From backend/
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
```

Docker (from **repo root**):

```bash
docker compose up --build
```

## Deploy

Railway config: `railway.toml` (Dockerfile + pre-deploy `alembic upgrade head`).
See [docs/operations.md](../docs/operations.md).

## Docs

- [API reference](../docs/api.md)
- [Model methodology](../docs/methodology.md)
- Root [README](../README.md)
