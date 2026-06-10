param(
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

if (-not (Test-Path $backendDir)) {
    throw "Backend directory not found at '$backendDir'."
}

$env:BASE_URL = $BaseUrl.TrimEnd("/")

Push-Location $backendDir
try {
    Write-Host "Running deploy smoke tests against $env:BASE_URL"
    uv run --extra dev pytest tests/smoke/ -v
} finally {
    Pop-Location
}
