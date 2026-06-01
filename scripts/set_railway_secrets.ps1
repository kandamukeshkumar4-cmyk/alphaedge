param(
    [Parameter(Mandatory = $true)]
    [string]$RailwayToken,
    [Parameter(Mandatory = $true)]
    [string]$NeonDatabaseUrl,
    [Parameter(Mandatory = $true)]
    [string]$AdminApiKey,
    [string]$NeonDatabaseUrlSync = "",
    [string]$Repo = "kandamukeshkumar4-cmyk/alphaedge",
    [string]$ApiUrl = "",
    [switch]$TriggerDeploy
)

$ErrorActionPreference = "Stop"

function Assert-SecretValue {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name is required."
    }
    if ($Value.Length -lt 8) {
        throw "$Name is too short to be a deploy secret."
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI was not found. Install gh and authenticate with repo + workflow scopes."
}

Assert-SecretValue "RAILWAY_TOKEN" $RailwayToken
Assert-SecretValue "NEON_DATABASE_URL" $NeonDatabaseUrl
Assert-SecretValue "ADMIN_API_KEY" $AdminApiKey

Write-Host "Setting Railway deployment secrets for $Repo."
gh secret set RAILWAY_TOKEN --repo $Repo --body $RailwayToken
gh secret set NEON_DATABASE_URL --repo $Repo --body $NeonDatabaseUrl
gh secret set ADMIN_API_KEY --repo $Repo --body $AdminApiKey

if (-not [string]::IsNullOrWhiteSpace($NeonDatabaseUrlSync)) {
    gh secret set NEON_DATABASE_URL_SYNC --repo $Repo --body $NeonDatabaseUrlSync
}

if ($TriggerDeploy) {
    Write-Host "Triggering Deploy Backend to Railway workflow."
    $fields = @("--field", "api_url=$ApiUrl")
    gh workflow run deploy-railway-backend.yml --repo $Repo --ref codex/alphaedge-base @fields
    Write-Host "Track the deployment with:"
    Write-Host "gh run list --repo $Repo --workflow deploy-railway-backend.yml --limit 3"
} else {
    Write-Host "Secrets set. Run Deploy Backend to Railway manually, or rerun this script with -TriggerDeploy."
}
