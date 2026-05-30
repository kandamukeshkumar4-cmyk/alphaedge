# Hugging Face Spaces + Neon Postgres

This is the current no-card backend unblock for AlphaEdge.

Frontend stays on Azure Static Web Apps:

```text
https://proud-meadow-01b42b810.7.azurestaticapps.net
```

Backend runs on a public Hugging Face Docker Space:

```text
https://mukeshkumarkanda-alphaedge-api.hf.space
```

Database runs on Neon Postgres.

## Current status

The Koyeb path remains documented in `docs/deploy/KOYEB_NEON.md`, but the
account setup flow required payment verification before deploying a service.
For the free/no-card portfolio demo path, use Hugging Face Spaces instead.

## Runtime secrets

Set these as private Hugging Face Space secrets, not repository files:

```text
PAPER_TRADING_ONLY=true
DATABASE_URL=<neon async SQLAlchemy URL>
DATABASE_URL_SYNC=<neon sync SQLAlchemy URL>
ADMIN_API_KEY=<long random secret>
```

The Space Dockerfile also sets:

```text
CORS_ORIGINS=https://proud-meadow-01b42b810.7.azurestaticapps.net
REDIS_URL=redis://disabled:6379/0
```

## Space Dockerfile

The Space uses Docker and listens on port `7860`. The current Space Dockerfile
clones the GitHub branch, installs the backend package, runs Alembic migrations,
and starts Uvicorn:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git gcc libpq-dev libgomp1 && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/kandamukeshkumar4-cmyk/alphaedge.git /app/alphaedge && cd /app/alphaedge && git checkout f9ba0a7

WORKDIR /app/alphaedge/backend

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/alphaedge/backend
ENV PAPER_TRADING_ONLY=true
ENV REDIS_URL=redis://disabled:6379/0
ENV CORS_ORIGINS=https://proud-meadow-01b42b810.7.azurestaticapps.net

EXPOSE 7860

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 7860
```

When promoting a new backend commit, update the pinned `git checkout` SHA in the
Space Dockerfile and rebuild the Space.

## Verify backend

```powershell
Invoke-RestMethod https://mukeshkumarkanda-alphaedge-api.hf.space/health
Invoke-RestMethod https://mukeshkumarkanda-alphaedge-api.hf.space/api/v1/markets
```

Expected:

```text
status=ok
paper_trading_only=true
Lakers vs Celtics market is returned
```

## Point frontend at the Space

Use the existing helper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_frontend_api_url.ps1 `
  -ApiUrl "https://mukeshkumarkanda-alphaedge-api.hf.space"
```

This sets:

```text
NEXT_PUBLIC_API_URL=https://mukeshkumarkanda-alphaedge-api.hf.space
```

Then it triggers the Azure Static Web Apps workflow with the same `api_url`
workflow input so the static Next.js export bakes in the backend URL.

## Verify frontend

```powershell
Invoke-WebRequest https://proud-meadow-01b42b810.7.azurestaticapps.net/markets
```

The page should show:

```text
Lakers vs Celtics - nba-2025-01-15-lal-bos (open)
```

## Limitations

- Hugging Face free CPU Spaces can sleep or cold start.
- This deploy runs the API only; no worker is attached to `REDIS_URL`.
- Keep the Space public for the portfolio demo unless you add an auth layer.
- This remains paper-trading only. No real-money trading, betting, or settlement is supported.
