param(
    [string]$RailwayToken = $env:RAILWAY_TOKEN,
    [string]$NeonDatabaseUrl = $env:NEON_DATABASE_URL,
    [string]$NeonDatabaseUrlSync = $env:NEON_DATABASE_URL_SYNC,
    [string]$AdminApiKey = $env:ADMIN_API_KEY,
    [string]$JwtSecretKey = $env:JWT_SECRET_KEY,
    [string]$ServiceName = "alphaedge-api",
    [string]$BackendDir = "backend",
    [string]$CorsOrigins = "https://proud-meadow-01b42b810.7.azurestaticapps.net",
    [string]$ApiUrl = "",
    [switch]$SkipDeploy
)

$ErrorActionPreference = "Stop"

function Assert-Configured {
    param(
        [string]$Name,
        [string]$Value,
        [string]$Help
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required. $Help"
    }
}

function Convert-ToAsyncPgUrl {
    param([string]$Url)

    if ($Url.StartsWith("postgresql+asyncpg://")) {
        return $Url
    }
    if ($Url.StartsWith("postgresql://")) {
        return $Url.Replace("postgresql://", "postgresql+asyncpg://")
    }
    if ($Url.StartsWith("postgres://")) {
        return $Url.Replace("postgres://", "postgresql+asyncpg://")
    }
    throw "NeonDatabaseUrl must start with postgresql://, postgres://, or postgresql+asyncpg://"
}

function Convert-ToSyncPgUrl {
    param([string]$Url)

    if ($Url.StartsWith("postgresql+asyncpg://")) {
        return $Url.Replace("postgresql+asyncpg://", "postgresql://")
    }
    if ($Url.StartsWith("postgres://")) {
        return $Url.Replace("postgres://", "postgresql://")
    }
    if ($Url.StartsWith("postgresql://")) {
        return $Url
    }
    throw "NeonDatabaseUrlSync must start with postgresql://, postgres://, or postgresql+asyncpg://"
}

Assert-Configured "RAILWAY_TOKEN" $RailwayToken "Create a Railway project token (Project Settings -> Tokens) and pass -RailwayToken or set RAILWAY_TOKEN."
Assert-Configured "NEON_DATABASE_URL" $NeonDatabaseUrl "Paste the Neon connection string or pass -NeonDatabaseUrl."
Assert-Configured "ADMIN_API_KEY" $AdminApiKey "Generate a long random value and pass -AdminApiKey or set ADMIN_API_KEY."
# C-SEC-03: with APP_ENV=production the backend boot-fails on the published
# dev-default JWT secret, so a real one is mandatory for any Railway deploy.
Assert-Configured "JWT_SECRET_KEY" $JwtSecretKey "Generate a long random value and pass -JwtSecretKey or set JWT_SECRET_KEY."

$railway = Get-Command railway -ErrorAction SilentlyContinue
if (-not $railway) {
    throw "Railway CLI was not found. Install it with 'npm i -g @railway/cli' (https://docs.railway.com/guides/cli), then rerun this script."
}

if (-not (Test-Path $BackendDir)) {
    throw "Backend directory '$BackendDir' was not found. Run this script from the repository root."
}

$databaseUrl = Convert-ToAsyncPgUrl $NeonDatabaseUrl
if ([string]::IsNullOrWhiteSpace($NeonDatabaseUrlSync)) {
    $databaseUrlSync = Convert-ToSyncPgUrl $NeonDatabaseUrl
} else {
    $databaseUrlSync = Convert-ToSyncPgUrl $NeonDatabaseUrlSync
}

# Railway reads RAILWAY_TOKEN (project token) from the environment to scope every command.
$env:RAILWAY_TOKEN = $RailwayToken

$variables = @(
    "PORT=8000",
    "PAPER_TRADING_ONLY=true",
    # Production posture: config validator refuses default secrets (C-SEC-03),
    # cookies get Secure, tokenless shared-account bypass is disabled (H-SEC-01).
    "APP_ENV=production",
    "DATABASE_URL=$databaseUrl",
    "DATABASE_URL_SYNC=$databaseUrlSync",
    "ADMIN_API_KEY=$AdminApiKey",
    "JWT_SECRET_KEY=$JwtSecretKey",
    "CORS_ORIGINS=$CorsOrigins",
    "REDIS_URL=redis://disabled:6379/0"
)

Write-Host "Setting AlphaEdge backend variables on Railway service '$ServiceName'. Secrets will not be printed."
$setArgs = @("variables", "--service", $ServiceName, "--skip-deploys")
foreach ($pair in $variables) {
    $setArgs += @("--set", $pair)
}
& railway @setArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to set Railway service variables. Confirm the project token and that service '$ServiceName' exists."
}

if ($SkipDeploy) {
    Write-Host "Variables set. Skipping deploy because -SkipDeploy was supplied."
    return
}

Push-Location $BackendDir
try {
    Write-Host "Deploying AlphaEdge backend to Railway service '$ServiceName' from '$BackendDir' (Dockerfile build)."
    & railway up --service $ServiceName --detach
    if ($LASTEXITCODE -ne 0) {
        throw "Railway deployment command failed."
    }
} finally {
    Pop-Location
}

if ([string]::IsNullOrWhiteSpace($ApiUrl)) {
    Write-Host "Deploy submitted. Generate or fetch the public URL with:"
    Write-Host "  railway domain --service $ServiceName"
    Write-Host "Then run: scripts/set_frontend_api_url.ps1 -ApiUrl https://<your-app>.up.railway.app"
    return
}

$ApiUrl = $ApiUrl.TrimEnd("/")
Write-Host "Checking $ApiUrl/health"
try {
    $health = Invoke-RestMethod -Method Get -Uri "$ApiUrl/health" -TimeoutSec 30
    Write-Host "Health status: $($health.status)"
} catch {
    Write-Warning "Deployment command finished, but /health was not reachable yet. Railway builds can take a few minutes to go live."
}

Write-Host "Backend URL: $ApiUrl"
Write-Host "Next: run scripts/set_frontend_api_url.ps1 -ApiUrl $ApiUrl"
