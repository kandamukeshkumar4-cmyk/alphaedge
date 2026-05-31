param(
    [string]$KoyebToken = $env:KOYEB_TOKEN,
    [string]$NeonDatabaseUrl = $env:NEON_DATABASE_URL,
    [string]$NeonDatabaseUrlSync = $env:NEON_DATABASE_URL_SYNC,
    [string]$AdminApiKey = $env:ADMIN_API_KEY,
    [string]$AppName = "alphaedge-api",
    [string]$ServiceName = "alphaedge-api",
    [string]$GitRepo = "github.com/kandamukeshkumar4-cmyk/alphaedge",
    [string]$GitBranch = "codex/alphaedge-base",
    [string]$CorsOrigins = "https://proud-meadow-01b42b810.7.azurestaticapps.net",
    [string]$Region = "was",
    [switch]$NoWait
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

Assert-Configured "KOYEB_TOKEN" $KoyebToken "Create a Koyeb API token and pass -KoyebToken or set KOYEB_TOKEN."
Assert-Configured "NEON_DATABASE_URL" $NeonDatabaseUrl "Paste the Neon connection string or pass -NeonDatabaseUrl."
Assert-Configured "ADMIN_API_KEY" $AdminApiKey "Generate a long random value and pass -AdminApiKey or set ADMIN_API_KEY."

$koyeb = Get-Command koyeb -ErrorAction SilentlyContinue
if (-not $koyeb) {
    throw "Koyeb CLI was not found. Install it from https://www.koyeb.com/docs/build-and-deploy/cli/installation, then rerun this script."
}

$databaseUrl = Convert-ToAsyncPgUrl $NeonDatabaseUrl
if ([string]::IsNullOrWhiteSpace($NeonDatabaseUrlSync)) {
    $databaseUrlSync = Convert-ToSyncPgUrl $NeonDatabaseUrl
} else {
    $databaseUrlSync = Convert-ToSyncPgUrl $NeonDatabaseUrlSync
}

$envArgs = @(
    "--env", "PORT=8000",
    "--env", "PAPER_TRADING_ONLY=true",
    "--env", "DATABASE_URL=$databaseUrl",
    "--env", "DATABASE_URL_SYNC=$databaseUrlSync",
    "--env", "ADMIN_API_KEY=$AdminApiKey",
    "--env", "CORS_ORIGINS=$CorsOrigins",
    "--env", "REDIS_URL=redis://disabled:6379/0"
)

$globalArgs = @("--token", $KoyebToken)

$deployArgs = @(
    "--git", $GitRepo,
    "--git-branch", $GitBranch,
    "--git-builder", "docker",
    "--git-workdir", "backend",
    "--git-docker-dockerfile", "Dockerfile",
    "--instance-type", "free",
    "--regions", $Region,
    "--ports", "8000:http",
    "--routes", "/:8000"
) + $envArgs

if (-not $NoWait) {
    $deployArgs += @("--wait", "--wait-timeout", "10m")
}

Write-Host "Deploying AlphaEdge backend to Koyeb app '$AppName' from $GitRepo@$GitBranch."
Write-Host "Using Koyeb free web instance in region '$Region'. Secrets will not be printed."

& koyeb @globalArgs apps get $AppName *> $null
$appExists = $LASTEXITCODE -eq 0
$serviceExists = $false

if ($appExists) {
    & koyeb @globalArgs services get "$AppName/$ServiceName" *> $null
    $serviceExists = $LASTEXITCODE -eq 0

    if ($serviceExists) {
        Write-Host "Koyeb app and service exist; updating service '$AppName/$ServiceName'."
    } else {
        Write-Host "Koyeb app exists but service '$ServiceName' is missing; creating service."
    }
} else {
    Write-Host "Koyeb app does not exist; creating app and service."
}

if ($appExists -and $serviceExists) {
    & koyeb @globalArgs services update "$AppName/$ServiceName" @deployArgs
} elseif ($appExists) {
    & koyeb @globalArgs services create $ServiceName --app $AppName @deployArgs
} else {
    & koyeb @globalArgs apps init $AppName @deployArgs
}

if ($LASTEXITCODE -ne 0) {
    throw "Koyeb deployment command failed."
}

$apiUrl = "https://$AppName.koyeb.app"
Write-Host "Checking $apiUrl/health"
try {
    $health = Invoke-RestMethod -Method Get -Uri "$apiUrl/health" -TimeoutSec 30
    Write-Host "Health status: $($health.status)"
} catch {
    Write-Warning "Deployment command finished, but /health was not reachable yet. Koyeb free instances can take a moment to wake up."
}

Write-Host "Backend URL: $apiUrl"
Write-Host "Next: run scripts/set_frontend_api_url.ps1 -ApiUrl $apiUrl"
