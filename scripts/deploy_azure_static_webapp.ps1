param(
    [string]$ResourceGroup = "alphaedge-static-rg",
    [string]$Location = "centralus",
    [string]$Name = "alphaedge-web",
    [string]$RepoUrl = "https://github.com/kandamukeshkumar4-cmyk/alphaedge",
    [string]$Branch = "codex/alphaedge-base"
)

$ErrorActionPreference = "Stop"

$token = gh auth token
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($token)) {
    throw "GitHub CLI token is required. Run gh auth login first."
}

az group create `
    --name $ResourceGroup `
    --location $Location `
    --tags project=alphaedge host=azure-static-web-apps
if ($LASTEXITCODE -ne 0) {
    throw "az group create failed"
}

az staticwebapp create `
    --name $Name `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Free `
    --source $RepoUrl `
    --branch $Branch `
    --token $token `
    --app-location frontend `
    --output-location out `
    --tags project=alphaedge
if ($LASTEXITCODE -ne 0) {
    throw "az staticwebapp create failed"
}

$hostname = az staticwebapp show `
    --name $Name `
    --resource-group $ResourceGroup `
    --query "defaultHostname" `
    --output tsv
if ($LASTEXITCODE -ne 0) {
    throw "az staticwebapp show failed"
}

Write-Output "Azure Static Web Apps URL: https://$hostname"
