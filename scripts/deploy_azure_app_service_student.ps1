param(
    [string]$ResourceGroup = "alphaedge-student-rg",
    [string]$Location = "centralus",
    [string]$NamePrefix = "alphaedge",
    [Parameter(Mandatory = $true)]
    [string]$AdminApiKey,
    [Parameter(Mandatory = $true)]
    [string]$PostgresPassword,
    [string]$CorsOrigins = "https://alphaedge.vercel.app"
)

$ErrorActionPreference = "Stop"

function Invoke-Az {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$AzArgs
    )

    & az @AzArgs
    if ($LASTEXITCODE -ne 0) {
        throw "az $($AzArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}

$account = az account show --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "az account show failed"
}

$safeSuffix = ($account.id -replace "[^a-zA-Z0-9]", "").Substring(0, 8).ToLowerInvariant()
$postgresServer = "$NamePrefix-pg-$safeSuffix"
$planName = "$NamePrefix-free-plan"
$webAppName = "$NamePrefix-api-$safeSuffix"
$backendPath = Resolve-Path "$PSScriptRoot\..\backend"
$zipPath = Join-Path ([System.IO.Path]::GetTempPath()) "$NamePrefix-backend.zip"

Invoke-Az group create --name $ResourceGroup --location $Location --tags project=alphaedge accountType="Azure for Students"

Invoke-Az postgres flexible-server update `
    --resource-group $ResourceGroup `
    --name $postgresServer `
    --admin-password $PostgresPassword

Invoke-Az appservice plan create `
    --resource-group $ResourceGroup `
    --name $planName `
    --location $Location `
    --is-linux `
    --sku F1

Invoke-Az webapp create `
    --resource-group $ResourceGroup `
    --plan $planName `
    --name $webAppName `
    --runtime "PYTHON:3.12"

$asyncDbUrl = "postgresql+asyncpg://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?ssl=require"
$syncDbUrl = "postgresql://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?sslmode=require"

Invoke-Az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $webAppName `
    --settings `
        "SCM_DO_BUILD_DURING_DEPLOYMENT=true" `
        "PAPER_TRADING_ONLY=true" `
        "ADMIN_API_KEY=$AdminApiKey" `
        "DATABASE_URL=$asyncDbUrl" `
        "DATABASE_URL_SYNC=$syncDbUrl" `
        "REDIS_URL=redis://disabled:6379/0" `
        "CORS_ORIGINS=$CorsOrigins"

Invoke-Az webapp config set `
    --resource-group $ResourceGroup `
    --name $webAppName `
    --startup-file "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) "$NamePrefix-backend-staging"
if (Test-Path $staging) {
    Remove-Item $staging -Recurse -Force
}
New-Item -ItemType Directory -Path $staging | Out-Null
robocopy $backendPath $staging /E /XD .venv __pycache__ .pytest_cache .ruff_cache backend /XF *.pyc | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force

Invoke-Az webapp deploy `
    --resource-group $ResourceGroup `
    --name $webAppName `
    --src-path $zipPath `
    --type zip

$hostname = Invoke-Az webapp show --resource-group $ResourceGroup --name $webAppName --query defaultHostName --output tsv
Write-Output "Azure App Service API URL: https://$hostname"
Write-Output "Health: https://$hostname/health"
