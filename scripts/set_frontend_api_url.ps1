param(
    [Parameter(Mandatory = $true)]
    [string]$ApiUrl,
    [string]$Repo = "kandamukeshkumar4-cmyk/alphaedge",
    [string]$Branch = "codex/alphaedge-base",
    [string]$Workflow = "azure-static-web-apps-proud-meadow-01b42b810.yml"
)

$ErrorActionPreference = "Stop"

if ($ApiUrl.EndsWith("/")) {
    $ApiUrl = $ApiUrl.TrimEnd("/")
}

if (-not ($ApiUrl.StartsWith("https://"))) {
    throw "ApiUrl must be an HTTPS URL, for example https://alphaedge-api.koyeb.app"
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI was not found. Install gh or set NEXT_PUBLIC_API_URL manually in the Azure Static Web Apps build environment."
}

Write-Host "Setting GitHub Actions secret NEXT_PUBLIC_API_URL for $Repo."
gh secret set NEXT_PUBLIC_API_URL --repo $Repo --body $ApiUrl

Write-Host "Triggering Azure Static Web Apps workflow on $Branch."
gh workflow run $Workflow --repo $Repo --ref $Branch --field api_url=$ApiUrl

Write-Host "Frontend redeploy requested. Track it with:"
Write-Host "gh run list --repo $Repo --workflow $Workflow --limit 3"
