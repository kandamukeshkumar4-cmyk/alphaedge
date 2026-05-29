# Azure Student + Vercel Deployment

This project stays paper-trading only. Do not deploy real-money trading, wallet, betting, or settlement features.

## Target Cloud Shape

- Backend API: Azure Container Apps, `min-replicas 0`, `max-replicas 1`.
- Container image: Azure Container Registry Standard.
- Database: Azure Database for PostgreSQL Flexible Server, Burstable `Standard_B1ms`, 32 GB storage.
- Frontend: Vercel production deployment from `frontend/`.
- Redis: local Docker only for now. The deployed API does not require Redis for `/health`, market listing, CLOB routes, or admin market lifecycle.

Microsoft's free-services page currently lists Container Apps monthly included usage as always free, App Service free web/API capacity as always free, Azure Container Registry Standard for 12 months, and Azure Database for PostgreSQL Flexible Server B1MS with 32 GB storage for 12 months. Student/free subscriptions can still incur charges when limits are exceeded or after the free period ends, so the Azure script creates a small Cost Management budget.

## Deploy Backend

```powershell
$AdminApiKey = "<generate-a-long-random-value>"
$PostgresPassword = "<generate-a-strong-password>"

powershell -ExecutionPolicy Bypass -File .\scripts\deploy_azure_student.ps1 `
  -AdminApiKey $AdminApiKey `
  -PostgresPassword $PostgresPassword `
  -CorsOrigins "https://your-vercel-app.vercel.app"
```

The script prints the Azure API URL and health URL.

## Deploy Frontend

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy_vercel.ps1 `
  -ApiUrl "https://your-azure-container-app-url"
```

## Post-Deploy Checks

```powershell
Invoke-RestMethod https://your-azure-container-app-url/health
Invoke-WebRequest https://your-vercel-app.vercel.app
```

Expected API health includes:

```json
{
  "status": "ok",
  "paper_trading_only": true
}
```
