# Koyeb Free Web Service + Neon Free Postgres

This is the non-Azure backend unblock for AlphaEdge.

Frontend stays on Azure Static Web Apps:

```text
https://proud-meadow-01b42b810.7.azurestaticapps.net
```

Backend runs on Koyeb as a Docker-built FastAPI web service. Database runs on Neon Postgres.

## 1. Create Neon Postgres

1. Create a free Neon project.
2. Open the Neon connection details for the project.
3. Copy the connection string.

Use the pooled Neon URL if it is available. Keep `sslmode=require` in the URL.

AlphaEdge needs both SQLAlchemy async and Alembic sync URLs:

```text
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DB?sslmode=require
DATABASE_URL_SYNC=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
```

The deploy script can derive these if you pass the standard Neon `postgresql://...` URL.

## 2. Deploy backend to Koyeb

Install the Koyeb CLI and create a Koyeb API token.

Required local environment:

```powershell
$env:KOYEB_TOKEN="koyeb_xxx"
$env:NEON_DATABASE_URL="postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
$env:ADMIN_API_KEY="use-a-long-random-secret"
```

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_koyeb_neon.ps1
```

The script deploys from:

```text
github.com/kandamukeshkumar4-cmyk/alphaedge
branch: codex/alphaedge-base
workdir: backend
Dockerfile: backend/Dockerfile
instance: free
region: was
```

Runtime env set on Koyeb:

```text
PAPER_TRADING_ONLY=true
DATABASE_URL=<neon asyncpg url>
DATABASE_URL_SYNC=<neon sync url>
ADMIN_API_KEY=<secret>
CORS_ORIGINS=https://proud-meadow-01b42b810.7.azurestaticapps.net
REDIS_URL=redis://disabled:6379/0
PORT=8000
```

Verify:

```powershell
Invoke-RestMethod https://alphaedge-api.koyeb.app/health
```

Expected:

```text
status=ok
paper_trading_only=true
```

### GitHub Actions deploy option

If you do not want to install the Koyeb CLI locally, set these GitHub repository secrets:

```text
KOYEB_TOKEN
NEON_DATABASE_URL
ADMIN_API_KEY
```

Optional:

```text
NEON_DATABASE_URL_SYNC
```

You can set the required GitHub secrets from this machine after creating the Neon DB and Koyeb token:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_koyeb_neon_secrets.ps1 `
  -KoyebToken "koyeb_xxx" `
  -NeonDatabaseUrl "postgresql://USER:PASSWORD@HOST/DB?sslmode=require" `
  -AdminApiKey "use-a-long-random-secret" `
  -TriggerDeploy
```

Then run the manual workflow:

```text
Deploy Backend to Koyeb
```

The workflow installs the Koyeb CLI on the GitHub runner, runs `scripts/deploy_koyeb_neon.ps1`, verifies `/health`, and then triggers the Azure Static Web Apps workflow with the same backend URL.

## 3. Preflight and final verification

Before and after running the Koyeb deploy, this command reports exactly what is
missing:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_koyeb_neon_ready.ps1
```

It checks:

```text
KOYEB_TOKEN, NEON_DATABASE_URL, ADMIN_API_KEY GitHub secrets
https://alphaedge-api.koyeb.app/health
https://alphaedge-api.koyeb.app/api/v1/markets
Azure Static Web Apps frontend bundle points at the Koyeb URL
```

If Koyeb returns `404: No active service`, the app hostname exists but the
backend service still needs to be created or redeployed.

## 4. Point Azure Static Web Apps frontend at Koyeb

After the Koyeb backend has a working HTTPS URL, this manual command is still available:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_frontend_api_url.ps1 -ApiUrl "https://alphaedge-api.koyeb.app"
```

This sets the GitHub Actions secret:

```text
NEXT_PUBLIC_API_URL=https://alphaedge-api.koyeb.app
```

Then it triggers the Azure Static Web Apps workflow. The workflow injects that secret at build time because the frontend is a static Next.js export.

If you use `Deploy Backend to Koyeb`, this frontend rebuild happens automatically and the API URL is passed as a workflow input.

## 5. Current limitations

- Koyeb free web services sleep after idle time.
- No worker is deployed on the Koyeb free service.
- `REDIS_URL=redis://disabled:6379/0` is only a placeholder for the API-only service; do not enable the worker without a real Redis provider.
- This remains paper-trading only with simulated funds and no external execution paths.
