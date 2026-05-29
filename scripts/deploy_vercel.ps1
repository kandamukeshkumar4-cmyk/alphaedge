param(
    [Parameter(Mandatory = $true)]
    [uri]$ApiUrl
)

$ErrorActionPreference = "Stop"
$apiUrlValue = $ApiUrl.AbsoluteUri.TrimEnd("/")

Push-Location "$PSScriptRoot\..\frontend"
try {
    vercel deploy --prod --yes `
        --build-env "NEXT_PUBLIC_API_URL=$apiUrlValue" `
        --env "NEXT_PUBLIC_API_URL=$apiUrlValue"
} finally {
    Pop-Location
}
