# Azure Container Apps Verification Script
# Checks health and readiness of all deployed services

param(
    [string]$EnvironmentName = "maala-acc",
    [string]$ResourceGroupName = "rg-maala-acc"
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

Write-Log "Azure Container Apps Verification Starting"

# Expected container apps
$containerApps = @(
    "ca-planner-$EnvironmentName",
    "ca-researcher-$EnvironmentName",
    "ca-writer-$EnvironmentName",
    "ca-reviewer-$EnvironmentName",
    "ca-supervisor-$EnvironmentName",
    "ca-orchestrator-$EnvironmentName"
)

# Expected resources
$expectedResources = @{
    "Storage Account" = "Microsoft.Storage/storageAccounts"
    "Container Registry" = "Microsoft.ContainerRegistry/registries"
    "Container Apps Environment" = "Microsoft.App/managedEnvironments"
    "Azure AI Search" = "Microsoft.Search/searchServices"
    "Cosmos DB Account" = "Microsoft.DocumentDB/databaseAccounts"
    "Log Analytics Workspace" = "Microsoft.OperationalInsights/workspaces"
    "Application Insights" = "Microsoft.Insights/components"
    "Key Vault" = "Microsoft.KeyVault/vaults"
}

Write-Log "Verifying resource group: $ResourceGroupName"

$rg = az group show --name $ResourceGroupName 2>$null
if ($rg) {
    Write-Log "Resource group found and accessible"
} else {
    Write-Log "Resource group not found or not accessible" "ERROR"
    exit 1
}

Write-Log "Listing all resources in resource group..."
$resources = az resource list --resource-group $ResourceGroupName --output json | ConvertFrom-Json

Write-Log "Total resources found: $($resources.Count)"

Write-Log "`n=== Resource Summary ==="
foreach ($resourceType in $expectedResources.Keys) {
    $type = $expectedResources[$resourceType]
    $count = ($resources | Where-Object { $_.type -eq $type }).Count
    $status = if ($count -gt 0) { "✓" } else { "✗" }
    Write-Host "$status ${resourceType}: $count"
}

Write-Log "`n=== Container Apps Status ==="

foreach ($appName in $containerApps) {
    Write-Log "Checking Container App: $appName"
    
    try {
        $app = az containerapp show --name $appName --resource-group $ResourceGroupName --output json -q 2>$null
        if ($app) {
            $appJson = $app | ConvertFrom-Json
            Write-Host "  Name: $($appJson.name)"
            Write-Host "  Provisioning State: $($appJson.properties.provisioningState)"
            Write-Host "  FQDN: $($appJson.properties.configuration.ingress.fqdn)"
            
            # Check replicas
            $replicas = $appJson.properties.template.scale.maxReplicas
            Write-Host "  Max Replicas: $replicas"
        } else {
            Write-Log "  Container App not found yet" "WARN"
        }
    } catch {
        Write-Log "  Error checking Container App: $_" "WARN"
    }
}

Write-Log "`n=== Deployment Outputs ==="

$deploymentFile = "deployment-outputs.json"
if (Test-Path $deploymentFile) {
    $outputs = Get-Content $deploymentFile | ConvertFrom-Json
    
    Write-Log "Container Registry: $($outputs.containerRegistryName.value)"
    Write-Log "Container Registry Endpoint: $($outputs.containerRegistryEndpoint.value)"
    Write-Log "Container Apps Environment: $($outputs.containerAppsEnvironmentName.value)"
    Write-Log "Application Insights: $($outputs.applicationInsightsName.value)"
    Write-Log "Cosmos DB Account: $($outputs.cosmosAccountName.value)"
    
    # Save outputs for later use
    $env:REGISTRY_NAME = $outputs.containerRegistryName.value
    $env:REGISTRY_ENDPOINT = $outputs.containerRegistryEndpoint.value
    $env:CONTAINER_APPS_ENV = $outputs.containerAppsEnvironmentName.value
    
    Write-Log "Environment variables exported for next steps"
} else {
    Write-Log "Deployment outputs file not found" "WARN"
}

Write-Log "Verification completed"
