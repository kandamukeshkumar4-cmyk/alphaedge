param(
    [string]$ResourceGroup = "alphaedge-student-rg",
    [string]$Location = "centralus",
    [string]$NamePrefix = "alphaedge",
    [Parameter(Mandatory = $true)]
    [string]$AdminApiKey,
    [Parameter(Mandatory = $true)]
    [string]$PostgresPassword,
    [string]$CorsOrigins = "http://localhost:3000",
    [int]$BudgetAmountUsd = 5
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

$account = az account show --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "az account show failed"
}
if ($account.name -notlike "*Azure for Students*") {
    Write-Warning "Current subscription is '$($account.name)', not Azure for Students. Review cost before continuing."
}

$assignmentId = "/subscriptions/$($account.id)/providers/Microsoft.Authorization/policyAssignments/sys.regionrestriction"
try {
    $policyUrl = "https://management.azure.com$assignmentId" + "?api-version=2022-06-01"
    $policyParams = Invoke-Az rest --method get --url $policyUrl --query "properties.parameters" --output json | ConvertFrom-Json
    $allowedLocations = @($policyParams.listOfAllowedLocations.value)
    if ($allowedLocations.Count -gt 0 -and $Location -notin $allowedLocations) {
        $preferred = @("centralus", "northcentralus", "southcentralus", "westus3", "mexicocentral")
        $Location = ($preferred | Where-Object { $_ -in $allowedLocations } | Select-Object -First 1)
        if (-not $Location) {
            $Location = $allowedLocations[0]
        }
        Write-Output "Using allowed Azure region from subscription policy: $Location"
    }
} catch {
    Write-Warning "Could not inspect allowed-location policy. Continuing with requested location '$Location'."
}

$safeSuffix = ($account.id -replace "[^a-zA-Z0-9]", "").Substring(0, 8).ToLowerInvariant()
$acrName = ("{0}{1}acr" -f ($NamePrefix -replace "[^a-zA-Z0-9]", ""), $safeSuffix).ToLowerInvariant()
$postgresServer = "$NamePrefix-pg-$safeSuffix"
$containerEnv = "$NamePrefix-env"
$containerApp = "$NamePrefix-api"
$imageName = "$NamePrefix-api"

Invoke-Az provider register --namespace Microsoft.App --wait
Invoke-Az provider register --namespace Microsoft.ContainerRegistry --wait
Invoke-Az provider register --namespace Microsoft.DBforPostgreSQL --wait

Invoke-Az group create --name $ResourceGroup --location $Location --tags project=alphaedge accountType="Azure for Students"

$today = Get-Date
$startDate = Get-Date -Year $today.Year -Month $today.Month -Day 1 -Format "yyyy-MM-dd"
$endDate = Get-Date -Year ($today.Year + 10) -Month 12 -Day 31 -Format "yyyy-MM-dd"
try {
    Invoke-Az consumption budget create `
        --budget-name "$NamePrefix-student-budget" `
        --category cost `
        --amount $BudgetAmountUsd `
        --time-grain Monthly `
        --start-date $startDate `
        --end-date $endDate `
        --resource-group-filter $ResourceGroup
} catch {
    Write-Warning "Budget creation failed. Create a manual Azure Cost Management budget before leaving resources running."
}

Invoke-Az acr create `
    --resource-group $ResourceGroup `
    --name $acrName `
    --sku Standard `
    --admin-enabled true

$loginServer = Invoke-Az acr show --resource-group $ResourceGroup --name $acrName --query loginServer --output tsv
Invoke-Az acr login --name $acrName

docker build -t "$loginServer/${imageName}:latest" ./backend
if ($LASTEXITCODE -ne 0) {
    throw "docker build failed with exit code $LASTEXITCODE"
}

docker push "$loginServer/${imageName}:latest"
if ($LASTEXITCODE -ne 0) {
    throw "docker push failed with exit code $LASTEXITCODE"
}

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

Invoke-Az containerapp env create `
    --resource-group $ResourceGroup `
    --name $containerEnv `
    --location $Location

$acrPassword = Invoke-Az acr credential show --resource-group $ResourceGroup --name $acrName --query "passwords[0].value" --output tsv
$asyncDbUrl = "postgresql+asyncpg://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?ssl=require"
$syncDbUrl = "postgresql://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?sslmode=require"

Invoke-Az containerapp create `
    --resource-group $ResourceGroup `
    --name $containerApp `
    --environment $containerEnv `
    --image "$loginServer/${imageName}:latest" `
    --registry-server $loginServer `
    --registry-username $acrName `
    --registry-password $acrPassword `
    --ingress external `
    --target-port 8000 `
    --min-replicas 0 `
    --max-replicas 1 `
    --cpu 0.25 `
    --memory 0.5Gi `
    --secrets "admin-api-key=$AdminApiKey" "database-url=$asyncDbUrl" "database-url-sync=$syncDbUrl" `
    --env-vars "PAPER_TRADING_ONLY=true" "ADMIN_API_KEY=secretref:admin-api-key" "DATABASE_URL=secretref:database-url" "DATABASE_URL_SYNC=secretref:database-url-sync" "REDIS_URL=redis://disabled:6379/0" "CORS_ORIGINS=$CorsOrigins"

$fqdn = Invoke-Az containerapp show --resource-group $ResourceGroup --name $containerApp --query "properties.configuration.ingress.fqdn" --output tsv
Write-Output "Azure API URL: https://$fqdn"
Write-Output "Health: https://$fqdn/health"
