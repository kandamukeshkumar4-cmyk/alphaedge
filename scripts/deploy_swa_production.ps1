param(
    [string]$ApiUrl = "https://mukeshkumarkanda-alphaedge-api.hf.space",
    [string]$ResourceGroup = "alphaedge-static-rg",
    [string]$Name = "alphaedge-web",
    [switch]$SkipApi
)

$ErrorActionPreference = "Stop"

if ($ApiUrl.EndsWith("/")) {
    $ApiUrl = $ApiUrl.TrimEnd("/")
}

if (-not ($ApiUrl.StartsWith("https://"))) {
    throw "ApiUrl must be an HTTPS URL."
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI is required. Run az login first."
}

$repoRoot = Split-Path $PSScriptRoot -Parent
$frontendDir = Join-Path $repoRoot "frontend"
$apiDir = Join-Path $repoRoot "api"

Write-Host "Building static frontend with NEXT_PUBLIC_API_URL=$ApiUrl"
$env:NEXT_PUBLIC_API_URL = $ApiUrl
Push-Location $frontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "frontend build failed"
    }
}
finally {
    Pop-Location
}

$deploymentToken = az staticwebapp secrets list `
    --name $Name `
    --resource-group $ResourceGroup `
    --query "properties.apiKey" `
    --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($deploymentToken)) {
    throw "Could not read Azure Static Web Apps deployment token."
}

$deployArgs = @(
    "--yes",
    "@azure/static-web-apps-cli",
    "deploy",
    "./frontend/out",
    "--deployment-token",
    $deploymentToken,
    "--env",
    "production"
)

if (-not $SkipApi) {
    $deployArgs += @(
        "--api-location",
        "./api",
        "--api-language",
        "node",
        "--api-version",
        "20"
    )
}

Write-Host "Deploying to Azure Static Web Apps ($Name)..."
Push-Location $repoRoot
try {
    & npx @deployArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Azure Static Web Apps deploy failed"
    }
}
finally {
    Pop-Location
}

$hostname = az staticwebapp show `
    --name $Name `
    --resource-group $ResourceGroup `
    --query "defaultHostname" `
    --output tsv

Write-Host "Deployment complete: https://$hostname"
