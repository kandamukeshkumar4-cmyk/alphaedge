param(
    [string]$ResourceGroup = "alphaedge-live-rg",
    [string]$Location = "westus3",
    [string]$NamePrefix = "alphaedge",
    [string]$NeonDatabaseUrl = $env:NEON_DATABASE_URL,
    [string]$NeonDatabaseUrlSync = $env:NEON_DATABASE_URL_SYNC,
    [string]$AdminApiKey = $env:ADMIN_API_KEY,
    [string]$PostgresPassword = $env:AZURE_POSTGRES_PASSWORD,
    [string]$CorsOrigins = "https://proud-meadow-01b42b810.7.azurestaticapps.net,http://localhost:3000",
    [switch]$SkipBuild,
    [switch]$UseAzurePostgres,
    [string]$ExistingContainerAppEnvId = ""
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

function New-Secret {
    param([int]$Length = 48)
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', 'x').Replace('/', 'y').Substring(0, $Length)
}

function Convert-ToAsyncPgUrl {
    param([string]$Url)
    if ($Url.StartsWith("postgresql+asyncpg://")) { return $Url }
    if ($Url.StartsWith("postgresql://")) {
        return $Url.Replace("postgresql://", "postgresql+asyncpg://")
    }
    if ($Url.StartsWith("postgres://")) {
        return $Url.Replace("postgres://", "postgresql+asyncpg://")
    }
    throw "Database URL must start with postgresql://, postgres://, or postgresql+asyncpg://"
}

function Convert-ToSyncPgUrl {
    param([string]$Url)
    if ($Url.StartsWith("postgresql+asyncpg://")) {
        return $Url.Replace("postgresql+asyncpg://", "postgresql://")
    }
    if ($Url.StartsWith("postgres://")) {
        return $Url.Replace("postgres://", "postgresql://")
    }
    if ($Url.StartsWith("postgresql://")) { return $Url }
    throw "Sync database URL must start with postgresql://, postgres://, or postgresql+asyncpg://"
}

$account = az account show --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "az account show failed - run az login first"
}

if ([string]::IsNullOrWhiteSpace($AdminApiKey) -or $AdminApiKey -eq "change-me-in-production") {
    $AdminApiKey = New-Secret
    Write-Host "Generated ADMIN_API_KEY (save this): $AdminApiKey"
}

$useNeon = -not [string]::IsNullOrWhiteSpace($NeonDatabaseUrl) -and -not $UseAzurePostgres
if (-not $useNeon) {
    if ([string]::IsNullOrWhiteSpace($PostgresPassword)) {
        $PostgresPassword = New-Secret 32
        Write-Host "Generated Azure Postgres password (save this): $PostgresPassword"
    }
}

$safeSuffix = ($account.id -replace "[^a-zA-Z0-9]", "").Substring(0, 8).ToLowerInvariant()
$acrName = ("{0}{1}acr" -f ($NamePrefix -replace "[^a-zA-Z0-9]", ""), $safeSuffix).ToLowerInvariant()
$postgresServer = "$NamePrefix-pg-$safeSuffix"
$containerEnv = "$NamePrefix-env"
$containerApp = "$NamePrefix-api"
$imageName = "$NamePrefix-api"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendPath = Join-Path $repoRoot "backend"

Invoke-Az provider register --namespace Microsoft.App --wait
Invoke-Az provider register --namespace Microsoft.ContainerRegistry --wait
if (-not $useNeon) {
    Invoke-Az provider register --namespace Microsoft.DBforPostgreSQL --wait
}

Invoke-Az group create --name $ResourceGroup --location $Location --tags project=alphaedge-live accountType="Azure for Students"

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$existingAcr = az acr show --resource-group $ResourceGroup --name $acrName --query name -o tsv 2>$null
$ErrorActionPreference = $prevEap
if (-not $existingAcr) {
    Invoke-Az acr create `
        --resource-group $ResourceGroup `
        --name $acrName `
        --sku Standard `
        --admin-enabled true
}

$loginServer = Invoke-Az acr show --resource-group $ResourceGroup --name $acrName --query loginServer --output tsv
$fullImage = "$loginServer/${imageName}:latest"

if (-not $SkipBuild) {
    $dockerRunning = $false
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        & docker version *> $null
        $dockerRunning = $LASTEXITCODE -eq 0
    }

    if ($dockerRunning) {
        Invoke-Az acr login --name $acrName
        docker build -t $fullImage $backendPath
        if ($LASTEXITCODE -ne 0) {
            throw "docker build failed with exit code $LASTEXITCODE"
        }
        docker push $fullImage
        if ($LASTEXITCODE -ne 0) {
            throw "docker push failed with exit code $LASTEXITCODE"
        }
    } else {
        Write-Host "Docker not running locally - building image in Azure (az acr build)..."
        Invoke-Az acr build `
            --registry $acrName `
            --image "${imageName}:latest" `
            --file (Join-Path $backendPath "Dockerfile") `
            $backendPath
    }
}

if ($useNeon) {
    $asyncDbUrl = Convert-ToAsyncPgUrl $NeonDatabaseUrl
    if ([string]::IsNullOrWhiteSpace($NeonDatabaseUrlSync)) {
        $syncDbUrl = Convert-ToSyncPgUrl $NeonDatabaseUrl
    } else {
        $syncDbUrl = Convert-ToSyncPgUrl $NeonDatabaseUrlSync
    }
    Write-Host "Using Neon DATABASE_URL from environment."
} else {
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $existingPg = az postgres flexible-server show --resource-group $ResourceGroup --name $postgresServer --query name -o tsv 2>$null
    $ErrorActionPreference = $prevEap
    if (-not $existingPg) {
        Invoke-Az postgres flexible-server create `
            --resource-group $ResourceGroup `
            --name $postgresServer `
            --location $Location `
            --admin-user alphaedgeadmin `
            --admin-password $PostgresPassword `
            --sku-name Standard_B1ms `
            --tier Burstable `
            --version 16 `
            --storage-size 32 `
            --public-access 0.0.0.0 `
            --yes

        Invoke-Az postgres flexible-server db create `
            --resource-group $ResourceGroup `
            --server-name $postgresServer `
            --database-name alphaedge
    } else {
        Invoke-Az postgres flexible-server update `
            --resource-group $ResourceGroup `
            --name $postgresServer `
            --admin-password $PostgresPassword
    }

    $asyncDbUrl = "postgresql+asyncpg://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?ssl=require"
    $syncDbUrl = "postgresql://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?sslmode=require"
}

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
if ([string]::IsNullOrWhiteSpace($ExistingContainerAppEnvId)) {
    $existingEnv = az containerapp env list --resource-group $ResourceGroup --query "[?name=='$containerEnv'].name" -o tsv 2>$null
    $ErrorActionPreference = $prevEap
    if (-not $existingEnv) {
        Write-Host "No Container App Environment in $ResourceGroup. Student subs allow 1 CAE total."
        Write-Host "Reuse an existing env: -ExistingContainerAppEnvId (az containerapp env show ... --query id -o tsv)"
        Invoke-Az containerapp env create `
            --resource-group $ResourceGroup `
            --name $containerEnv `
            --location $Location
    }
    $containerAppEnv = $containerEnv
} else {
    $containerAppEnv = $ExistingContainerAppEnvId
}

$acrPassword = Invoke-Az acr credential show --resource-group $ResourceGroup --name $acrName --query "passwords[0].value" --output tsv
$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$existingApp = az containerapp show --resource-group $ResourceGroup --name $containerApp 2>$null
$appExists = $LASTEXITCODE -eq 0 -and $existingApp
$ErrorActionPreference = $prevEap

if ($appExists) {
    Invoke-Az containerapp update `
        --resource-group $ResourceGroup `
        --name $containerApp `
        --image $fullImage `
        --min-replicas 1 `
        --max-replicas 1 `
        --set-env-vars `
            "PAPER_TRADING_ONLY=true" `
            "ADMIN_API_KEY=secretref:admin-api-key" `
            "DATABASE_URL=secretref:database-url" `
            "DATABASE_URL_SYNC=secretref:database-url-sync" `
            "REDIS_URL=redis://disabled:6379/0" `
            "CORS_ORIGINS=$CorsOrigins" `
            "LIVE_FEED_ENABLED=true" `
            "LIVE_TICK_INTERVAL_SEC=15" `
            "LIVE_INGEST_INTERVAL_SEC=1800" `
            "LIVE_INGEST_TOTAL_LIMIT=100" `
            "LIVE_INGEST_MIN_VOLUME_24H=10000"
} else {
    Invoke-Az containerapp create `
        --resource-group $ResourceGroup `
        --name $containerApp `
        --environment $containerAppEnv `
        --image $fullImage `
        --registry-server $loginServer `
        --registry-username $acrName `
        --registry-password $acrPassword `
        --ingress external `
        --target-port 8000 `
        --min-replicas 1 `
        --max-replicas 1 `
        --cpu 0.5 `
        --memory 1.0Gi `
        --secrets "admin-api-key=$AdminApiKey" "database-url=$asyncDbUrl" "database-url-sync=$syncDbUrl" `
        --env-vars `
            "PAPER_TRADING_ONLY=true" `
            "ADMIN_API_KEY=secretref:admin-api-key" `
            "DATABASE_URL=secretref:database-url" `
            "DATABASE_URL_SYNC=secretref:database-url-sync" `
            "REDIS_URL=redis://disabled:6379/0" `
            "CORS_ORIGINS=$CorsOrigins" `
            "LIVE_FEED_ENABLED=true" `
            "LIVE_TICK_INTERVAL_SEC=15" `
            "LIVE_INGEST_INTERVAL_SEC=1800" `
            "LIVE_INGEST_TOTAL_LIMIT=100" `
            "LIVE_INGEST_MIN_VOLUME_24H=10000"
}

$fqdn = Invoke-Az containerapp show --resource-group $ResourceGroup --name $containerApp --query "properties.configuration.ingress.fqdn" --output tsv
$apiUrl = "https://$fqdn"
$wsUrl = "wss://$fqdn"

Write-Output ""
Write-Output "=== AlphaEdge live backend deployed ==="
Write-Output "API URL:  $apiUrl"
Write-Output "WS URL:   $wsUrl"
Write-Output "Health:   $apiUrl/health"
Write-Output ""
Write-Output "Next: update frontend env and redeploy static site with NEXT_PUBLIC_API_URL and NEXT_PUBLIC_WS_URL"

# Write deploy summary without secrets
$summaryPath = Join-Path $repoRoot "deploy-azure-live-summary.txt"
@(
    "deployed_at=$(Get-Date -Format o)"
    "api_url=$apiUrl"
    "ws_url=$wsUrl"
    "resource_group=$ResourceGroup"
    "location=$Location"
    "container_app=$containerApp"
) | Set-Content -Path $summaryPath -Encoding utf8
Write-Output "Summary saved to deploy-azure-live-summary.txt"
