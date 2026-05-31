param(
    [string]$Repo = "kandamukeshkumar4-cmyk/alphaedge",
    [string]$ApiUrl = "https://alphaedge-api.koyeb.app",
    [string]$FrontendUrl = "https://proud-meadow-01b42b810.7.azurestaticapps.net",
    [switch]$SkipGitHubSecrets,
    [switch]$SkipFrontendCheck
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]

function Add-Failure {
    param([string]$Message)
    $failures.Add($Message) | Out-Null
    Write-Warning $Message
}

function Get-GitHubSecretNames {
    param([string]$Repository)

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI was not found. Install gh or rerun with -SkipGitHubSecrets."
    }

    $lines = gh secret list --repo $Repository
    if ($LASTEXITCODE -ne 0) {
        throw "Could not list GitHub secrets for $Repository."
    }

    return $lines | ForEach-Object { ($_ -split "\s+")[0] } | Where-Object { $_ }
}

if (-not $ApiUrl.StartsWith("https://")) {
    Add-Failure "ApiUrl must be HTTPS: $ApiUrl"
}

if (-not $SkipGitHubSecrets) {
    $secretNames = @(Get-GitHubSecretNames -Repository $Repo)
    foreach ($required in @("KOYEB_TOKEN", "NEON_DATABASE_URL", "ADMIN_API_KEY")) {
        if ($secretNames -notcontains $required) {
            Add-Failure "Missing GitHub secret: $required"
        }
    }
}

try {
    $health = Invoke-RestMethod -Method Get -Uri "$ApiUrl/health" -TimeoutSec 30
    if ($health.status -ne "ok") {
        Add-Failure "Koyeb health returned status '$($health.status)', expected 'ok'."
    }
    if ($health.paper_trading_only -ne $true) {
        Add-Failure "Koyeb health did not report paper_trading_only=true."
    }
} catch {
    $body = ""
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
        $body = $_.ErrorDetails.Message
    }
    if ($body -match "No active service") {
        Add-Failure "Koyeb app exists but has no active service at $ApiUrl."
    } else {
        Add-Failure "Koyeb health check failed for $ApiUrl/health: $($_.Exception.Message)"
    }
}

try {
    $markets = Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/v1/markets" -TimeoutSec 30
    $hasCanonicalMarket = @($markets) | Where-Object { $_.slug -eq "nba-2025-01-15-lal-bos" }
    if (-not $hasCanonicalMarket) {
        Add-Failure "Koyeb API did not return the canonical Lakers vs Celtics market."
    }
} catch {
    Add-Failure "Koyeb markets check failed for $ApiUrl/api/v1/markets: $($_.Exception.Message)"
}

if (-not $SkipFrontendCheck) {
    try {
        $page = Invoke-WebRequest -Method Get -Uri "$FrontendUrl/markets" -TimeoutSec 30
        $chunkPaths = @(
            [regex]::Matches($page.Content, 'src="([^"]*app/markets/page-[^"]+\.js)"') |
                ForEach-Object { $_.Groups[1].Value }
        )

        if (-not $chunkPaths) {
            Add-Failure "Could not find the deployed markets page JavaScript chunk."
        } else {
            $chunkUrl = if ($chunkPaths[0].StartsWith("http")) {
                $chunkPaths[0]
            } else {
                "$FrontendUrl$($chunkPaths[0])"
            }
            $chunk = Invoke-WebRequest -Method Get -Uri $chunkUrl -TimeoutSec 30
            if ($chunk.Content -notmatch [regex]::Escape($ApiUrl)) {
                Add-Failure "Frontend markets bundle is not pointed at $ApiUrl."
            }
        }
    } catch {
        Add-Failure "Frontend check failed for $FrontendUrl/markets: $($_.Exception.Message)"
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Koyeb/Neon readiness: FAILED"
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "Koyeb/Neon readiness: OK"
Write-Host "Backend: $ApiUrl"
Write-Host "Frontend: $FrontendUrl"
