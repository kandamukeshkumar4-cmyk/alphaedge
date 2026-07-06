param(
    [string]$ApiUrl = "https://mukeshkumar007-alphaedge-api.hf.space",
    [string]$FrontendUrl = "https://proud-meadow-01b42b810.7.azurestaticapps.net",
    [string]$MarketSlug = "nba-2025-01-15-lal-bos",
    [string]$ElectionSlug = "elect-la-mayor-2026",
    [string]$AdminApiKey = $env:ADMIN_API_KEY,
    [switch]$SkipAdminProof,
    [switch]$SkipFrontendCheck,
    [int]$TimeoutSec = 30,
    [int]$MaxAttempts = 40,
    [int]$RetryDelaySec = 15
)

$ErrorActionPreference = "Stop"
$failures = New-Object System.Collections.Generic.List[string]
$ApiUrl = $ApiUrl.TrimEnd([char]"/")
$FrontendUrl = $FrontendUrl.TrimEnd([char]"/")

function Add-Failure {
    param([string]$Message)
    $failures.Add($Message) | Out-Null
    Write-Warning $Message
}

function Invoke-Json {
    param(
        [ValidateSet("Get", "Post")]
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null,
        [hashtable]$Headers = @{}
    )

    $parameters = @{
        Method = $Method
        Uri = $Uri
        TimeoutSec = $TimeoutSec
        Headers = $Headers
    }
    if ($null -ne $Body) {
        $parameters.Body = ($Body | ConvertTo-Json -Depth 10)
        $parameters.ContentType = "application/json"
    }

    return Invoke-RestMethod @parameters
}

function Invoke-JsonWithRetry {
    param(
        [string]$Label,
        [scriptblock]$Operation
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt += 1) {
        try {
            return & $Operation
        } catch {
            if ($attempt -ge $MaxAttempts) {
                throw
            }
            Write-Host "Attempt $attempt/${MaxAttempts}: $Label failed: $($_.Exception.Message); retrying in $RetryDelaySec sec"
            Start-Sleep -Seconds $RetryDelaySec
        }
    }
}

function Expand-JsonArray {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }
    if ($Value -is [System.Array]) {
        return @($Value)
    }
    return @($Value)
}

function Assert-FutureMarketLock {
    param(
        [object]$Market,
        [string]$Slug
    )

    if (-not $Market.lock_at) {
        Add-Failure "$Slug did not return lock_at; browser paper trading cannot prove start-window risk."
        return
    }

    try {
        $lockAt = [DateTimeOffset]::Parse([string]$Market.lock_at)
    } catch {
        Add-Failure "$Slug returned unparsable lock_at '$($Market.lock_at)'."
        return
    }

    if ($lockAt -le [DateTimeOffset]::UtcNow.AddMinutes(5)) {
        Add-Failure "$Slug lock_at must be in the future for browser paper trading; got '$($Market.lock_at)'."
    }
}

try {
    $health = Invoke-JsonWithRetry -Label "HF health" -Operation {
        Invoke-Json -Method Get -Uri "$ApiUrl/health"
    }
    if ($health.status -ne "ok") {
        Add-Failure "HF health returned status '$($health.status)', expected 'ok'."
    }
    if ($health.paper_trading_only -ne $true) {
        Add-Failure "HF health did not report paper_trading_only=true."
    }
} catch {
    Add-Failure "HF health check failed for $ApiUrl/health: $($_.Exception.Message)"
}

try {
    $marketsPayload = Invoke-JsonWithRetry -Label "HF markets" -Operation {
        Invoke-Json -Method Get -Uri "$ApiUrl/api/v1/markets"
    }
    $markets = @(Expand-JsonArray -Value $marketsPayload)
    $canonical = $markets | Where-Object { $_.slug -eq $MarketSlug } | Select-Object -First 1
    $election = $markets | Where-Object { $_.slug -eq $ElectionSlug } | Select-Object -First 1
    if (-not $canonical) {
        Add-Failure "HF markets endpoint did not return $MarketSlug."
    } else {
        Assert-FutureMarketLock -Market $canonical -Slug $MarketSlug
    }
    if (-not $election) {
        Add-Failure "HF markets endpoint did not return $ElectionSlug."
    } elseif ($election.category -ne "Politics") {
        Add-Failure "Expected $ElectionSlug to be in Politics, got '$($election.category)'."
    }
} catch {
    Add-Failure "HF markets check failed for $ApiUrl/api/v1/markets: $($_.Exception.Message)"
}

try {
    $snapshot = Invoke-JsonWithRetry -Label "HF election snapshot" -Operation {
        Invoke-Json -Method Get -Uri "$ApiUrl/api/v1/markets/$ElectionSlug/snapshot"
    }
    if ($snapshot.market.slug -ne $ElectionSlug) {
        Add-Failure "Expected election snapshot to return $ElectionSlug."
    }
    if ($snapshot.paper_trading_only -ne $true) {
        Add-Failure "Expected election snapshot to report paper_trading_only=true."
    }
} catch {
    Add-Failure "HF election snapshot failed for $ApiUrl/api/v1/markets/$ElectionSlug/snapshot: $($_.Exception.Message)"
}

if (-not $SkipFrontendCheck) {
    try {
        $page = Invoke-JsonWithRetry -Label "frontend markets page" -Operation {
            Invoke-WebRequest -Method Get -Uri "$FrontendUrl/markets" -TimeoutSec $TimeoutSec
        }
        $chunkPaths = @(
            [regex]::Matches($page.Content, 'src="([^"]*\.js)"') |
                ForEach-Object { $_.Groups[1].Value } |
                Where-Object { $_ -match "/_next/static/" } |
                Select-Object -Unique
        )

        if (-not $chunkPaths) {
            Add-Failure "Could not find deployed frontend JavaScript chunks."
        } else {
            $foundApiUrl = $false
            foreach ($path in $chunkPaths) {
                $chunkUrl = if ($path.StartsWith("http")) { $path } else { "$FrontendUrl$path" }
                $chunk = Invoke-JsonWithRetry -Label "frontend chunk $chunkUrl" -Operation {
                    Invoke-WebRequest -Method Get -Uri $chunkUrl -TimeoutSec $TimeoutSec
                }
                if ($chunk.Content -match [regex]::Escape($ApiUrl)) {
                    $foundApiUrl = $true
                    break
                }
            }
            if (-not $foundApiUrl) {
                Add-Failure "Frontend markets bundle is not pointed at $ApiUrl."
            }
        }
    } catch {
        Add-Failure "Frontend bundle check failed for $FrontendUrl/markets: $($_.Exception.Message)"
    }
}

$orderId = $null
$smokeAccountId = $null
try {
    $publicAccount = Invoke-JsonWithRetry -Label "paper account" -Operation {
        Invoke-Json -Method Get -Uri "$ApiUrl/api/v1/paper-account"
    }
    if ($publicAccount.paper_trading_only -ne $true) {
        Add-Failure "Expected paper account endpoint to report paper_trading_only=true."
    }

    if (-not $AdminApiKey) {
        throw "AdminApiKey is required for isolated smoke account order lifecycle."
    }

    $account = Invoke-JsonWithRetry -Label "admin smoke account" -Operation {
        Invoke-Json `
            -Method Get `
            -Uri "$ApiUrl/admin/smoke-account" `
            -Headers @{ "X-Admin-API-Key" = $AdminApiKey }
    }
    if ($account.name -ne "Deployment Smoke Account") {
        Add-Failure "Expected admin smoke account, got '$($account.name)'."
    }
    if ($account.paper_trading_only -ne $true) {
        Add-Failure "Expected admin smoke account endpoint to report paper_trading_only=true."
    }
    $smokeAccountId = $account.id
    if (-not $smokeAccountId) {
        throw "Admin smoke account did not return an id."
    }

    $order = Invoke-JsonWithRetry -Label "paper order create" -Operation {
        Invoke-Json `
            -Method Post `
            -Uri "$ApiUrl/api/v1/markets/$MarketSlug/orders" `
            -Body @{
                account_id = $smokeAccountId
                side = "buy"
                outcome = "yes"
                order_type = "limit"
                quantity = "1"
                price = "0.01"
                risk = @{
                    predicted_prob = 0.62
                    confidence = 0.8
                    edge = 0.07
                    current_drawdown = 0
                    minutes_before_start = 120
                }
            }
    }
    $orderId = $order.id
    if (-not $orderId) {
        throw "Paper order did not return an id."
    }
    if ($order.status -ne "open") {
        Add-Failure "Expected risk-gated paper order to open, got '$($order.status)'."
    }
    if ($order.account_id -ne $smokeAccountId) {
        Add-Failure "Paper order did not bind to the smoke-test account."
    }
} catch {
    Add-Failure "Paper order lifecycle create step failed: $($_.Exception.Message)"
} finally {
    if ($orderId -and $smokeAccountId) {
        try {
            $cancelled = Invoke-JsonWithRetry -Label "paper order cancel" -Operation {
                Invoke-Json `
                    -Method Post `
                    -Uri "$ApiUrl/api/v1/orders/$orderId/cancel" `
                    -Body @{ account_id = $smokeAccountId }
            }
            if ($cancelled.status -ne "cancelled") {
                Add-Failure "Expected cancellation to release smoke-test order, got '$($cancelled.status)'."
            }
        } catch {
            Add-Failure "Smoke order cancellation failed for ${orderId}: $($_.Exception.Message)"
        }
    }
}

if ($orderId) {
    try {
        $afterCancel = Invoke-JsonWithRetry -Label "post-cancel admin smoke account" -Operation {
            Invoke-Json `
                -Method Get `
                -Uri "$ApiUrl/admin/smoke-account" `
                -Headers @{ "X-Admin-API-Key" = $AdminApiKey }
        }
        $stillOpen = @($afterCancel.open_orders) | Where-Object { $_.id -eq $orderId }
        if ($stillOpen) {
            Add-Failure "Smoke paper order was not removed from open orders after cancel."
        }

        $publicAfterCancel = Invoke-JsonWithRetry -Label "post-cancel public paper account" -Operation {
            Invoke-Json -Method Get -Uri "$ApiUrl/api/v1/paper-account"
        }
        $publicOpen = @($publicAfterCancel.open_orders) | Where-Object { $_.id -eq $orderId }
        $publicHistory = @($publicAfterCancel.order_history) | Where-Object { $_.id -eq $orderId }
        if ($publicOpen -or $publicHistory) {
            Add-Failure "Smoke paper order leaked into the public paper account."
        }
    } catch {
        Add-Failure "Post-cancel smoke account check failed: $($_.Exception.Message)"
    }
}

if (-not $SkipAdminProof) {
    if (-not $AdminApiKey) {
        Add-Failure "AdminApiKey is required for admin agent proof; pass -SkipAdminProof for public checks."
    } else {
        try {
            $proof = Invoke-JsonWithRetry -Label "admin agent proof" -Operation {
                Invoke-Json `
                    -Method Post `
                    -Uri "$ApiUrl/admin/agents/run/$MarketSlug" `
                    -Headers @{ "X-Admin-API-Key" = $AdminApiKey }
            }

            if ($proof.market_slug -ne $MarketSlug) {
                Add-Failure "Expected agent proof for $MarketSlug."
            }
            if ([string]$proof.disclaimer -notmatch "paper-trading simulation") {
                Add-Failure "Expected paper-trading simulation disclaimer from agent proof."
            }
            if ($proof.status -ne "blocked" -or $proof.approved -ne $false) {
                Add-Failure "Expected deployed agent proof to remain blocked by risk."
            }

            $riskStep = @($proof.steps) | Where-Object { $_.step_name -eq "risk" } | Select-Object -First 1
            if (-not $riskStep) {
                Add-Failure "Expected risk step in deployed agent proof."
            } else {
                $riskOutput = $riskStep.output_data
                if ($riskOutput.approved -ne $false) {
                    Add-Failure "Expected deployed risk step to reject weak edge."
                }
                $riskErrors = @($riskOutput.errors) -join " "
                if ($riskErrors -notmatch "edge") {
                    Add-Failure "Expected deployed risk step to report edge rejection."
                }
            }

            $proofJson = $proof | ConvertTo-Json -Depth 20
            if ($proofJson -match "order_id|execution_id") {
                Add-Failure "Deployed agent proof unexpectedly created execution artifacts."
            }
        } catch {
            Add-Failure "Admin agent proof failed for $ApiUrl/admin/agents/run/${MarketSlug}: $($_.Exception.Message)"
        }
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "HF paper-trading readiness: FAILED"
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "HF paper-trading readiness: OK"
Write-Host "Backend: $ApiUrl"
Write-Host "Frontend: $FrontendUrl"
Write-Host "Market: $MarketSlug"
