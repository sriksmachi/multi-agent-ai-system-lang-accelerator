# Azure Infrastructure Deployment Script
# Deploys all Azure resources for multi-agent AI system using Bicep templates
# Run this FIRST before deploy-apps.ps1

param(
    [string]$EnvironmentName = "maala-acc",
    [string]$Location = "westus2",
    [string]$SubscriptionId = "090fcc3a-ed78-4e98-a932-974261d033e2"
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Log function
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

Write-Log "Azure Infrastructure Deployment Starting"
Write-Log "Environment: $EnvironmentName"
Write-Log "Location: $Location"
Write-Log "Subscription: $SubscriptionId"

# Set subscription
az account set --subscription $SubscriptionId
Write-Log "Subscription set to: $SubscriptionId"

# Get principal ID
$principalId = az ad signed-in-user show --query id -o tsv
Write-Log "Principal ID: $principalId"

# Create resource group
$resourceGroupName = "rg-$EnvironmentName"
Write-Log "Creating/checking resource group: $resourceGroupName"

$rgExists = az group exists --name $resourceGroupName
if ($rgExists -eq "true") {
    Write-Log "Resource group already exists"
} else {
    az group create --name $resourceGroupName --location $Location
    Write-Log "Resource group created"
}

# Set environment variables for deployment
$env:AZURE_ENV_NAME = $EnvironmentName
$env:AZURE_LOCATION = $Location
$env:AZURE_PRINCIPAL_ID = $principalId
$env:AZURE_OPENAI_API_KEY = ""

# Get absolute paths
$infraPath = $PSScriptRoot
$templatePath = Join-Path $infraPath "resources.bicep"
$parametersPath = Join-Path $infraPath "main.parameters.json"

Write-Log "Template path: $templatePath"
Write-Log "Parameters path: $parametersPath"

# Replace environment variables in parameters
Write-Log "Preparing deployment parameters..."
$paramsContent = Get-Content $parametersPath -Raw
$paramsContent = $paramsContent -replace '\$\{AZURE_ENV_NAME\}', $EnvironmentName
$paramsContent = $paramsContent -replace '\$\{AZURE_LOCATION\}', $Location
$paramsContent = $paramsContent -replace '\$\{AZURE_PRINCIPAL_ID\}', $principalId
$paramsContent = $paramsContent -replace '\$\{AZURE_OPENAI_API_KEY\}', $env:AZURE_OPENAI_API_KEY
$tmpParamsFile = Join-Path $infraPath "main.parameters.temp.json"
Set-Content -Path $tmpParamsFile -Value $paramsContent

Write-Log "Deploying Azure resources..."
Write-Log "This may take 15-20 minutes..."

$deploymentName = "deploy-$(Get-Date -Format 'yyyyMMddHHmmss')"

try {
    $output = az deployment group create `
        --name $deploymentName `
        --resource-group $resourceGroupName `
        --template-file $templatePath `
        --parameters $tmpParamsFile `
        --output json
    
    $outputJson = $output | ConvertFrom-Json
    
    Write-Log "Deployment completed successfully"
    Write-Log "Deployment name: $deploymentName"
    
    # Extract outputs
    $outputs = $outputJson.properties.outputs
    
    Write-Log "Container Registry Name: $($outputs.containerRegistryName.value)"
    Write-Log "Container Apps Environment: $($outputs.containerAppsEnvironmentName.value)"
    Write-Log "Container Registry Endpoint: $($outputs.containerRegistryEndpoint.value)"
    
    # Save outputs to file (in project root)
    $outputFile = Join-Path (Split-Path $infraPath -Parent) "deployment-outputs.json"
    $outputJson.properties.outputs | ConvertTo-Json | Set-Content -Path $outputFile
    Write-Log "Outputs saved to: $outputFile"
    
} catch {
    Write-Log "Deployment failed: $_" "ERROR"
    exit 1
} finally {
    # Clean up temp parameters file
    if (Test-Path $tmpParamsFile) {
        Remove-Item $tmpParamsFile
    }
}

Write-Log "Infrastructure deployment completed"
Write-Log ""
Write-Log "Next step: Run deploy-apps.ps1 from the project root to deploy application containers"
