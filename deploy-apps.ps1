# Deploy All Agent Services to Azure Container Apps
# This script publishes latest images to container apps (default) or builds and deploys all containers
# Prerequisites: Run infra/deploy-all.ps1 first to provision Azure infrastructure
#
# Usage:
#   .\deploy-apps.ps1                        # Deploy latest images for all services
#   .\deploy-apps.ps1 -Build                 # Build and deploy all services
#   .\deploy-apps.ps1 -Service orchestrator  # Deploy only orchestrator
#   .\deploy-apps.ps1 -Build -Service planner # Build and deploy only planner

param(
    [string]$ResourceGroup = "rg-maala-acc",
    [string]$EnvironmentName = "maala-acc",
    [switch]$Build,
    [ValidateSet("planner", "researcher", "writer", "reviewer", "supervisor", "orchestrator", "")]
    [string]$Service = ""
)

# Ensure we're logged in
Write-Host "🔐 Checking Azure login..." -ForegroundColor Cyan
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not logged in to Azure. Running 'az login'..." -ForegroundColor Red
    az login
}

# Get environment variables from azd if not provided
if ([string]::IsNullOrEmpty($ResourceGroup)) {
    Write-Host "📋 Getting resource group from azd environment..." -ForegroundColor Cyan
    $ResourceGroup = azd env get-values | Select-String "AZURE_RESOURCE_GROUP" | ForEach-Object { ($_ -split '=')[1].Trim('"') }
}

if ([string]::IsNullOrEmpty($EnvironmentName)) {
    Write-Host "📋 Getting environment name from azd environment..." -ForegroundColor Cyan
    $EnvironmentName = azd env get-values | Select-String "AZURE_ENV_NAME" | ForEach-Object { ($_ -split '=')[1].Trim('"') }
}

# Validate resource group
if ([string]::IsNullOrEmpty($ResourceGroup)) {
    Write-Host "❌ Resource group is empty. Please run 'azd up' first or provide -ResourceGroup parameter." -ForegroundColor Red
    exit 1
}

# Get container registry name
Write-Host "📋 Getting container registry info..." -ForegroundColor Cyan
$registryName = az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv

if ([string]::IsNullOrEmpty($registryName)) {
    Write-Host "❌ No container registry found in resource group '$ResourceGroup'." -ForegroundColor Red
    Write-Host "   Please run 'azd up' or 'infra/deploy-all.ps1' first to provision Azure infrastructure." -ForegroundColor Red
    exit 1
}

$registryServer = "$registryName.azurecr.io"

Write-Host ""
Write-Host "🚀 Deployment Configuration:" -ForegroundColor Green
Write-Host "   Resource Group: $ResourceGroup"
Write-Host "   Environment: $EnvironmentName"
Write-Host "   Registry: $registryServer"
Write-Host "   Build Images: $Build"
Write-Host "   Service: $(if ($Service) { $Service } else { 'all' })"
Write-Host ""

# Generate a single timestamp for this deployment (ensures consistency)
$deployTimestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Write-Host "📅 Deployment Timestamp: $deployTimestamp" -ForegroundColor Cyan

$allImages = @(
    @{Name="planner-agent"; Dockerfile="agents/planner_agent/Dockerfile"; Service="planner"},
    @{Name="researcher-agent"; Dockerfile="agents/researcher_agent/Dockerfile"; Service="researcher"},
    @{Name="writer-agent"; Dockerfile="agents/writer_agent/Dockerfile"; Service="writer"},
    @{Name="reviewer-agent"; Dockerfile="agents/reviewer_agent/Dockerfile"; Service="reviewer"},
    @{Name="supervisor-agent"; Dockerfile="agents/supervisor/Dockerfile"; Service="supervisor"},
    @{Name="orchestrator-api"; Dockerfile="Dockerfile"; Service="orchestrator"}
)

# Filter to single service if specified
if ($Service) {
    $images = $allImages | Where-Object { $_.Service -eq $Service }
} else {
    $images = $allImages
}

# Build and push images (only if -Build flag is specified)
if ($Build) {
    Write-Host "🔨 Building and pushing container images..." -ForegroundColor Yellow
    
    foreach ($image in $images) {
        Write-Host ""
        Write-Host "📦 Building $($image.Name)..." -ForegroundColor Cyan
        az acr build --registry $registryName --image "$($image.Name):latest" --image "$($image.Name):$deployTimestamp" --file $image.Dockerfile .
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to build $($image.Name)" -ForegroundColor Red
            exit 1
        }
        Write-Host "✅ Built $($image.Name):$deployTimestamp" -ForegroundColor Green
    }
} else {
    Write-Host "⏭️  Skipping build (use -Build flag to rebuild images)" -ForegroundColor Yellow
    # When not building, use latest tag
    $deployTimestamp = "latest"
}

# Update container apps
Write-Host ""
Write-Host "🔄 Updating Container Apps..." -ForegroundColor Yellow

$allApps = @(
    @{Name="ca-planner-$EnvironmentName"; Image="planner-agent"; Service="planner"},
    @{Name="ca-researcher-$EnvironmentName"; Image="researcher-agent"; Service="researcher"},
    @{Name="ca-writer-$EnvironmentName"; Image="writer-agent"; Service="writer"},
    @{Name="ca-reviewer-$EnvironmentName"; Image="reviewer-agent"; Service="reviewer"},
    @{Name="ca-supervisor-$EnvironmentName"; Image="supervisor-agent"; Service="supervisor"},
    @{Name="ca-orchestrator-$EnvironmentName"; Image="orchestrator-api"; Service="orchestrator"}
)

# Filter to single service if specified
if ($Service) {
    $apps = $allApps | Where-Object { $_.Service -eq $Service }
} else {
    $apps = $allApps
}

foreach ($app in $apps) {
    Write-Host ""
    Write-Host "🔄 Updating $($app.Name) with image tag :$deployTimestamp ..." -ForegroundColor Cyan
    
    az containerapp update --name $app.Name --resource-group $ResourceGroup --image "$registryServer/$($app.Image):$deployTimestamp"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  Warning: Failed to update $($app.Name)" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Updated $($app.Name)" -ForegroundColor Green
    }
}

# Get service URLs
Write-Host ""
Write-Host "🌐 Getting service URLs..." -ForegroundColor Cyan

Write-Host ""
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host ""

# Show URLs for deployed services
if (-not $Service -or $Service -eq "orchestrator") {
    $orchestratorUrl = az containerapp show --name "ca-orchestrator-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    Write-Host "📍 Orchestrator API: https://$orchestratorUrl" -ForegroundColor Cyan
    Write-Host "   curl https://$orchestratorUrl/"
}
if (-not $Service -or $Service -eq "supervisor") {
    $supervisorUrl = az containerapp show --name "ca-supervisor-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    Write-Host "📍 Supervisor Agent: https://$supervisorUrl" -ForegroundColor Cyan
    Write-Host "   curl https://$supervisorUrl/"
}
if (-not $Service -or $Service -eq "planner") {
    $plannerUrl = az containerapp show --name "ca-planner-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    Write-Host "📍 Planner Agent:    https://$plannerUrl" -ForegroundColor Cyan
    Write-Host "   curl https://$plannerUrl/"
}
if (-not $Service -or $Service -eq "researcher") {
    $researcherUrl = az containerapp show --name "ca-researcher-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    Write-Host "📍 Researcher Agent: https://$researcherUrl" -ForegroundColor Cyan
    Write-Host "   curl https://$researcherUrl/"
}
if (-not $Service -or $Service -eq "writer") {
    $writerUrl = az containerapp show --name "ca-writer-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    Write-Host "📍 Writer Agent:     https://$writerUrl" -ForegroundColor Cyan
    Write-Host "   curl https://$writerUrl/"
}
if (-not $Service -or $Service -eq "reviewer") {
    $reviewerUrl = az containerapp show --name "ca-reviewer-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv
    Write-Host "📍 Reviewer Agent:   https://$reviewerUrl" -ForegroundColor Cyan
    Write-Host "   curl https://$reviewerUrl/"
}

Write-Host ""
Write-Host "📊 Monitor in Application Insights:" -ForegroundColor Yellow
Write-Host "   az portal show --resource-group $ResourceGroup --resource-type Microsoft.Insights/components"
Write-Host ""
