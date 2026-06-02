param(
    [string]$HfToken = "",
    [string]$NeonDatabaseUrl = "",
    [string]$AdminApiKey = "",
    [string]$NeonDatabaseUrlSync = "",
    [string]$Repo = "kandamukeshkumar4-cmyk/alphaedge",
    [switch]$SetNeonDatabaseUrlSync,
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

function Set-GitHubSecret {
    param(
        [string]$Name,
        [string]$Value,
        [switch]$Required
    )

    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        Assert-SecretValue $Name $Value
        gh secret set $Name --repo $Repo --body $Value
        return
    }

    if ($script:ExistingSecrets.ContainsKey($Name)) {
        Write-Host "$Name already exists on $Repo; leaving it unchanged."
        return
    }

    if (-not $Required) {
        return
    }

    Write-Host "Paste $Name when prompted by GitHub CLI. Input is not printed."
    gh secret set $Name --repo $Repo
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI was not found. Install gh and authenticate with repo + workflow scopes."
}

$script:ExistingSecrets = @{}
gh secret list --repo $Repo | ForEach-Object {
    $name = ($_ -split "\s+")[0]
    if (-not [string]::IsNullOrWhiteSpace($name)) {
        $script:ExistingSecrets[$name] = $true
    }
}

Write-Host "Setting Hugging Face Space deployment secrets for $Repo."
Set-GitHubSecret "HF_TOKEN" $HfToken -Required
Set-GitHubSecret "NEON_DATABASE_URL" $NeonDatabaseUrl -Required
Set-GitHubSecret "ADMIN_API_KEY" $AdminApiKey -Required

if ($SetNeonDatabaseUrlSync -or -not [string]::IsNullOrWhiteSpace($NeonDatabaseUrlSync)) {
    Set-GitHubSecret "NEON_DATABASE_URL_SYNC" $NeonDatabaseUrlSync -Required
}

if ($TriggerDeploy) {
    Write-Host "Triggering Deploy Backend to HF Space workflow."
    gh workflow run deploy-hf-space.yml --repo $Repo --ref codex/alphaedge-base
    Write-Host "Track the deployment with:"
    Write-Host "gh run list --repo $Repo --workflow deploy-hf-space.yml --limit 3"
} else {
    Write-Host "Secrets set. Run Deploy Backend to HF Space manually, or rerun this script with -TriggerDeploy."
}
