# Deploy All Agent Services to Azure Container Apps
# This script builds and deploys all agent containers and the orchestrator

param(
    [string]$ResourceGroup = "",
    [string]$EnvironmentName = ""
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

# Get container registry name
Write-Host "📋 Getting container registry info..." -ForegroundColor Cyan
$registryName = az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv
$registryServer = "$registryName.azurecr.io"

Write-Host ""
Write-Host "🚀 Deployment Configuration:" -ForegroundColor Green
Write-Host "   Resource Group: $ResourceGroup"
Write-Host "   Environment: $EnvironmentName"
Write-Host "   Registry: $registryServer"
Write-Host ""

# Build and push images
Write-Host "🔨 Building and pushing container images..." -ForegroundColor Yellow

$images = @(
    @{Name="planner-agent"; Dockerfile="agents/planner_agent/Dockerfile"},
    @{Name="researcher-agent"; Dockerfile="agents/researcher_agent/Dockerfile"},
    @{Name="writer-agent"; Dockerfile="agents/writer_agent/Dockerfile"},
    @{Name="reviewer-agent"; Dockerfile="agents/reviewer_agent/Dockerfile"},
    @{Name="supervisor-agent"; Dockerfile="agents/supervisor/Dockerfile"},
    @{Name="orchestrator-api"; Dockerfile="Dockerfile"}
)

foreach ($image in $images) {
    Write-Host ""
    Write-Host "📦 Building $($image.Name)..." -ForegroundColor Cyan
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    az acr build --registry $registryName --image "$($image.Name):latest" --image "$($image.Name):$timestamp" --file $image.Dockerfile .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to build $($image.Name)" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Built $($image.Name)" -ForegroundColor Green
}

# Update container apps
Write-Host ""
Write-Host "🔄 Updating Container Apps..." -ForegroundColor Yellow

$apps = @(
    @{Name="ca-planner-$EnvironmentName"; Image="planner-agent"},
    @{Name="ca-researcher-$EnvironmentName"; Image="researcher-agent"},
    @{Name="ca-writer-$EnvironmentName"; Image="writer-agent"},
    @{Name="ca-reviewer-$EnvironmentName"; Image="reviewer-agent"},
    @{Name="ca-supervisor-$EnvironmentName"; Image="supervisor-agent"},
    @{Name="ca-orchestrator-$EnvironmentName"; Image="orchestrator-api"}
)

foreach ($app in $apps) {
    Write-Host ""
    Write-Host "🔄 Updating $($app.Name)..." -ForegroundColor Cyan
    
    az containerapp update --name $app.Name --resource-group $ResourceGroup --image "$registryServer/$($app.Image):latest"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️  Warning: Failed to update $($app.Name)" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Updated $($app.Name)" -ForegroundColor Green
    }
}

# Get orchestrator URL
Write-Host ""
Write-Host "🌐 Getting service URLs..." -ForegroundColor Cyan
$orchestratorUrl = az containerapp show --name "ca-orchestrator-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

$supervisorUrl = az containerapp show --name "ca-supervisor-$EnvironmentName" --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Orchestrator API: https://$orchestratorUrl" -ForegroundColor Cyan
Write-Host "📍 Supervisor Agent: https://$supervisorUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "🧪 Test the deployment:" -ForegroundColor Yellow
Write-Host "   curl https://$orchestratorUrl/health"
Write-Host "   curl https://$supervisorUrl/health"
Write-Host "   curl https://$supervisorUrl/agents"
Write-Host ""
Write-Host "📊 Monitor in Application Insights:" -ForegroundColor Yellow
Write-Host "   az portal show --resource-group $ResourceGroup --resource-type Microsoft.Insights/components"
Write-Host ""
