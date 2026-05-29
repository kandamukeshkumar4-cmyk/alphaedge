param(
    [string]$ResourceGroup = "alphaedge-student-rg",
    [string]$Location = "eastus",
    [string]$NamePrefix = "alphaedge",
    [Parameter(Mandatory = $true)]
    [string]$AdminApiKey,
    [Parameter(Mandatory = $true)]
    [string]$PostgresPassword,
    [string]$CorsOrigins = "http://localhost:3000",
    [int]$BudgetAmountUsd = 5
)

$ErrorActionPreference = "Stop"

$account = az account show --output json | ConvertFrom-Json
if ($account.name -notlike "*Azure for Students*") {
    Write-Warning "Current subscription is '$($account.name)', not Azure for Students. Review cost before continuing."
}

$safeSuffix = ($account.id -replace "[^a-zA-Z0-9]", "").Substring(0, 8).ToLowerInvariant()
$acrName = ("{0}{1}acr" -f ($NamePrefix -replace "[^a-zA-Z0-9]", ""), $safeSuffix).ToLowerInvariant()
$postgresServer = "$NamePrefix-pg-$safeSuffix"
$containerEnv = "$NamePrefix-env"
$containerApp = "$NamePrefix-api"
$imageName = "$NamePrefix-api"

az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.DBforPostgreSQL --wait

az group create --name $ResourceGroup --location $Location --tags project=alphaedge accountType="Azure for Students"

$today = Get-Date
$startDate = Get-Date -Year $today.Year -Month $today.Month -Day 1 -Format "yyyy-MM-dd"
$endDate = Get-Date -Year ($today.Year + 10) -Month 12 -Day 31 -Format "yyyy-MM-dd"
try {
    az consumption budget create `
        --resource-group $ResourceGroup `
        --budget-name "$NamePrefix-student-budget" `
        --amount $BudgetAmountUsd `
        --time-grain Monthly `
        --start-date $startDate `
        --end-date $endDate
} catch {
    Write-Warning "Budget creation failed. Create a manual Azure Cost Management budget before leaving resources running."
}

az acr create `
    --resource-group $ResourceGroup `
    --name $acrName `
    --sku Standard `
    --admin-enabled true

az acr build `
    --registry $acrName `
    --image "${imageName}:latest" `
    ./backend

az postgres flexible-server create `
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

az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $postgresServer `
    --database-name alphaedge

az containerapp env create `
    --resource-group $ResourceGroup `
    --name $containerEnv `
    --location $Location

$loginServer = az acr show --resource-group $ResourceGroup --name $acrName --query loginServer -o tsv
$acrPassword = az acr credential show --resource-group $ResourceGroup --name $acrName --query "passwords[0].value" -o tsv
$asyncDbUrl = "postgresql+asyncpg://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?ssl=require"
$syncDbUrl = "postgresql://alphaedgeadmin:$PostgresPassword@$postgresServer.postgres.database.azure.com:5432/alphaedge?sslmode=require"

az containerapp create `
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

$fqdn = az containerapp show --resource-group $ResourceGroup --name $containerApp --query "properties.configuration.ingress.fqdn" -o tsv
Write-Output "Azure API URL: https://$fqdn"
Write-Output "Health: https://$fqdn/health"
