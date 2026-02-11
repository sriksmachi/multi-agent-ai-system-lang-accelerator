# Configure RBAC for Azure Container Apps with User-Assigned Managed Identity
# This script creates a user-assigned managed identity and grants access to downstream services
#
# Usage:
#   .\configure-rbac.ps1
#   .\configure-rbac.ps1 -ResourceGroup "my-rg" -EnvironmentName "dev"

param(
    [string]$ResourceGroup = "rg-maala-acc",
    [string]$EnvironmentName = "maala-acc",
    [string]$IdentityName = ""
)

# Ensure we're logged in
Write-Host "🔐 Checking Azure login..." -ForegroundColor Cyan
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not logged in to Azure. Running 'az login'..." -ForegroundColor Red
    az login
}

# Get subscription ID and location
$subscriptionId = az account show --query "id" -o tsv
$location = az group show --name $ResourceGroup --query "location" -o tsv

# Set default identity name if not provided
if ([string]::IsNullOrEmpty($IdentityName)) {
    $IdentityName = "id-agents-$EnvironmentName"
}

Write-Host ""
Write-Host "🚀 RBAC Configuration:" -ForegroundColor Green
Write-Host "   Resource Group: $ResourceGroup"
Write-Host "   Environment: $EnvironmentName"
Write-Host "   Identity Name: $IdentityName"
Write-Host "   Location: $location"
Write-Host ""

# ============================================================================
# Create User-Assigned Managed Identity
# ============================================================================
Write-Host "🔑 Creating User-Assigned Managed Identity..." -ForegroundColor Yellow

$existingIdentity = az identity show --name $IdentityName --resource-group $ResourceGroup 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Identity '$IdentityName' already exists" -ForegroundColor Gray
} else {
    az identity create --name $IdentityName --resource-group $ResourceGroup --location $location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create managed identity" -ForegroundColor Red
        exit 1
    }
    Write-Host "   ✅ Created identity: $IdentityName" -ForegroundColor Green
    
    # Wait for identity to propagate
    Write-Host "   ⏳ Waiting for identity to propagate..." -ForegroundColor Gray
    Start-Sleep -Seconds 30
}

# Get identity details
$identityId = az identity show --name $IdentityName --resource-group $ResourceGroup --query "id" -o tsv
$identityClientId = az identity show --name $IdentityName --resource-group $ResourceGroup --query "clientId" -o tsv
$identityPrincipalId = az identity show --name $IdentityName --resource-group $ResourceGroup --query "principalId" -o tsv

Write-Host "   Identity ID: $identityId" -ForegroundColor Gray
Write-Host "   Client ID: $identityClientId" -ForegroundColor Gray
Write-Host "   Principal ID: $identityPrincipalId" -ForegroundColor Gray

# ============================================================================
# Get Azure Resources
# ============================================================================
Write-Host ""
Write-Host "📋 Getting Azure resource info..." -ForegroundColor Cyan

# Get container registry info
$registryName = az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv
$registryId = az acr show --name $registryName --resource-group $ResourceGroup --query "id" -o tsv 2>$null

if ([string]::IsNullOrEmpty($registryName)) {
    Write-Host "   ⚠️  No container registry found" -ForegroundColor Yellow
} else {
    Write-Host "   Registry: $registryName" -ForegroundColor Green
}

# Get Key Vault info
$keyVaultName = az keyvault list --resource-group $ResourceGroup --query "[0].name" -o tsv 2>$null
$keyVaultId = az keyvault show --name $keyVaultName --resource-group $ResourceGroup --query "id" -o tsv 2>$null

if ([string]::IsNullOrEmpty($keyVaultName)) {
    Write-Host "   ⚠️  No Key Vault found" -ForegroundColor Yellow
} else {
    Write-Host "   Key Vault: $keyVaultName" -ForegroundColor Green
}

# Get Azure OpenAI info
$openAiName = az cognitiveservices account list --resource-group $ResourceGroup --query "[?kind=='OpenAI'].name | [0]" -o tsv 2>$null
$openAiId = az cognitiveservices account show --name $openAiName --resource-group $ResourceGroup --query "id" -o tsv 2>$null

if ([string]::IsNullOrEmpty($openAiName)) {
    Write-Host "   ⚠️  No Azure OpenAI found" -ForegroundColor Yellow
} else {
    Write-Host "   Azure OpenAI: $openAiName" -ForegroundColor Green
}

# Get Cosmos DB info
$cosmosName = az cosmosdb list --resource-group $ResourceGroup --query "[0].name" -o tsv 2>$null
$cosmosId = az cosmosdb show --name $cosmosName --resource-group $ResourceGroup --query "id" -o tsv 2>$null

if ([string]::IsNullOrEmpty($cosmosName)) {
    Write-Host "   ⚠️  No Cosmos DB found" -ForegroundColor Yellow
} else {
    Write-Host "   Cosmos DB: $cosmosName" -ForegroundColor Green
}

# Get AI Search info
$searchName = az search service list --resource-group $ResourceGroup --query "[0].name" -o tsv 2>$null
$searchId = az search service show --name $searchName --resource-group $ResourceGroup --query "id" -o tsv 2>$null

if ([string]::IsNullOrEmpty($searchName)) {
    Write-Host "   ⚠️  No AI Search found" -ForegroundColor Yellow
} else {
    Write-Host "   AI Search: $searchName" -ForegroundColor Green
}

# Get Container Apps Environment
$envName = az containerapp env list --resource-group $ResourceGroup --query "[0].name" -o tsv

if ([string]::IsNullOrEmpty($envName)) {
    Write-Host "❌ No Container Apps Environment found in resource group '$ResourceGroup'." -ForegroundColor Red
    exit 1
}
Write-Host "   CA Environment: $envName" -ForegroundColor Green

# ============================================================================
# Grant RBAC Roles to User-Assigned Identity
# ============================================================================
Write-Host ""
Write-Host "🔧 Granting RBAC roles to managed identity..." -ForegroundColor Yellow

# ACR Pull
if (-not [string]::IsNullOrEmpty($registryId)) {
    Write-Host "   Granting AcrPull on Container Registry..." -ForegroundColor Gray
    az role assignment create --assignee $identityPrincipalId --role "AcrPull" --scope $registryId 2>$null
}

# Key Vault Secrets User
if (-not [string]::IsNullOrEmpty($keyVaultId)) {
    Write-Host "   Granting Key Vault Secrets User..." -ForegroundColor Gray
    az role assignment create --assignee $identityPrincipalId --role "Key Vault Secrets User" --scope $keyVaultId 2>$null
}

# Azure OpenAI User
if (-not [string]::IsNullOrEmpty($openAiId)) {
    Write-Host "   Granting Cognitive Services OpenAI User..." -ForegroundColor Gray
    az role assignment create --assignee $identityPrincipalId --role "Cognitive Services OpenAI User" --scope $openAiId 2>$null
}

# Cosmos DB Data Contributor
if (-not [string]::IsNullOrEmpty($cosmosId)) {
    Write-Host "   Granting Cosmos DB Built-in Data Contributor..." -ForegroundColor Gray
    az cosmosdb sql role assignment create --account-name $cosmosName --resource-group $ResourceGroup --role-definition-id "00000000-0000-0000-0000-000000000002" --principal-id $identityPrincipalId --scope "/" 2>$null
}

# AI Search Index Data Contributor
if (-not [string]::IsNullOrEmpty($searchId)) {
    Write-Host "   Granting Search Index Data Contributor..." -ForegroundColor Gray
    az role assignment create --assignee $identityPrincipalId --role "Search Index Data Contributor" --scope $searchId 2>$null
}

Write-Host "   ✅ RBAC roles assigned" -ForegroundColor Green

# ============================================================================
# Assign User-Assigned Identity to Container Apps
# ============================================================================
Write-Host ""
Write-Host "🔗 Assigning identity to Container Apps..." -ForegroundColor Yellow

$apps = @(
    "ca-planner-$EnvironmentName",
    "ca-researcher-$EnvironmentName",
    "ca-writer-$EnvironmentName",
    "ca-reviewer-$EnvironmentName",
    "ca-supervisor-$EnvironmentName",
    "ca-orchestrator-$EnvironmentName"
)

foreach ($appName in $apps) {
    Write-Host ""
    Write-Host "🔄 Configuring $appName..." -ForegroundColor Cyan
    
    # Check if app exists
    $appExists = az containerapp show --name $appName --resource-group $ResourceGroup 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ⚠️  App not found, skipping..." -ForegroundColor Yellow
        continue
    }
    
    # Assign user-assigned managed identity
    Write-Host "   Assigning user-assigned identity..." -ForegroundColor Gray
    az containerapp identity assign --name $appName --resource-group $ResourceGroup --user-assigned $identityId 2>$null
    
    # Configure the container app to use the registry with user-assigned identity
    if (-not [string]::IsNullOrEmpty($registryName)) {
        Write-Host "   Configuring ACR registry access..." -ForegroundColor Gray
        az containerapp registry set --name $appName --resource-group $ResourceGroup --server "$registryName.azurecr.io" --identity $identityId 2>$null
    }
    
    # Set identity client ID as environment variable for SDK authentication
    Write-Host "   Setting AZURE_CLIENT_ID environment variable..." -ForegroundColor Gray
    az containerapp update --name $appName --resource-group $ResourceGroup --set-env-vars "AZURE_CLIENT_ID=$identityClientId" 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Configured $appName" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Warning: Configuration may have partially failed for $appName" -ForegroundColor Yellow
    }
}

# ============================================================================
# Summary
# ============================================================================
Write-Host ""
Write-Host "✅ RBAC configuration complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Summary:" -ForegroundColor Cyan
Write-Host "   Identity: $IdentityName"
Write-Host "   Client ID: $identityClientId"
Write-Host ""
Write-Host "   Roles granted:" -ForegroundColor Cyan
if (-not [string]::IsNullOrEmpty($registryName)) { Write-Host "   - AcrPull on $registryName" }
if (-not [string]::IsNullOrEmpty($keyVaultName)) { Write-Host "   - Key Vault Secrets User on $keyVaultName" }
if (-not [string]::IsNullOrEmpty($openAiName)) { Write-Host "   - Cognitive Services OpenAI User on $openAiName" }
if (-not [string]::IsNullOrEmpty($cosmosName)) { Write-Host "   - Cosmos DB Data Contributor on $cosmosName" }
if (-not [string]::IsNullOrEmpty($searchName)) { Write-Host "   - Search Index Data Contributor on $searchName" }
Write-Host ""
Write-Host "🚀 You can now run .\deploy-apps.ps1 to deploy images" -ForegroundColor Yellow
Write-Host ""
