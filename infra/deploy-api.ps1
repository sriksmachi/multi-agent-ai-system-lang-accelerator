# Requires -Version 7.0

param(
    [string]$ResourceGroupName="sriks-ml-rg",
    [string]$AppServiceName="socialmediagenerator-api",
    [string]$Location = "southeastasia",
    [string]$AppServicePlan="socialmediagenerator-api-plan",
    [string]$Sku = "S1",
    [string]$EnvFilePath = "../.env",
    [string]$AcrName="socialmediageneratoracr",
    [string]$ImageName = "socialmediagenerator-api",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "FastAPI Container Deployment to Azure App Service" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path $EnvFilePath)) {
    Write-Host "❌ .env file not found at: $EnvFilePath" -ForegroundColor Red
    exit 1
}

# Check if Azure CLI is installed
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed. Please install it from https://aka.ms/azure-cli" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Azure CLI is installed" -ForegroundColor Green

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Please install it from https://www.docker.com/get-started" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Docker is installed" -ForegroundColor Green

# Check if logged in to Azure
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "❌ Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Azure login failed" -ForegroundColor Red
        exit 1
    }
    $account = az account show | ConvertFrom-Json
}

Write-Host "✅ Logged in to Azure as: $($account.user.name)" -ForegroundColor Green
Write-Host "   Subscription: $($account.name) ($($account.id))" -ForegroundColor White
Write-Host ""

# Prompt for parameters if not provided
if (-not $ResourceGroupName) {
    $ResourceGroupName = Read-Host "Enter Resource Group Name"
}

if (-not $AcrName) {
    $AcrName = "$($AppServiceName -replace '[^a-zA-Z0-9]', '')acr"
}

# Ensure ACR name is valid (alphanumeric, 5-50 chars)
$AcrName = $AcrName.ToLower() -replace '[^a-z0-9]', ''
if ($AcrName.Length -lt 5) {
    $AcrName = "${AcrName}$(Get-Random -Minimum 10000 -Maximum 99999)"
}
$AcrName = $AcrName.Substring(0, [Math]::Min(50, $AcrName.Length))

Write-Host "📋 Deployment Configuration:" -ForegroundColor Cyan
Write-Host "   Resource Group: $ResourceGroupName" -ForegroundColor White
Write-Host "   App Service Name: $AppServiceName" -ForegroundColor White
Write-Host "   App Service Plan: $AppServicePlan" -ForegroundColor White
Write-Host "   Container Registry: $AcrName" -ForegroundColor White
Write-Host "   Image: $ImageName $ImageTag" -ForegroundColor White
Write-Host "   Location: $Location" -ForegroundColor White

if (-not $AppServicePlan) {
    $AppServicePlan = "$AppServiceName-plan"
}

# Create Resource Group if it doesn't exist
Write-Host "📦 Checking Resource Group..." -ForegroundColor Cyan
$rgExists = az group exists --name $ResourceGroupName | ConvertFrom-Json
if (-not $rgExists) {
    Write-Host "   Creating Resource Group: $ResourceGroupName" -ForegroundColor Yellow
    az group create --name $ResourceGroupName --location $Location --output none
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Resource Group created" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create Resource Group" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ Resource Group exists" -ForegroundColor Green
}
Write-Host ""

# Create Azure Container Registry if it doesn't exist
Write-Host "📦 Checking Azure Container Registry..." -ForegroundColor Cyan
$acrExists = az acr show --name $AcrName --resource-group $ResourceGroupName 2>$null
if (-not $acrExists) {
    Write-Host "   Creating Azure Container Registry: $AcrName" -ForegroundColor Yellow
    az acr create `
        --name $AcrName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku Basic `
        --admin-enabled true `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Azure Container Registry created" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create Azure Container Registry" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ Azure Container Registry exists" -ForegroundColor Green
    # Ensure admin is enabled
    az acr update --name $AcrName --resource-group $ResourceGroupName --admin-enabled true --output none
}
Write-Host ""

# Get ACR credentials
Write-Host "🔑 Getting ACR credentials..." -ForegroundColor Cyan
$acrCredentials = az acr credential show --name $AcrName --resource-group $ResourceGroupName | ConvertFrom-Json
$acrLoginServer = az acr show --name $AcrName --resource-group $ResourceGroupName --query loginServer -o tsv
Write-Host "✅ ACR credentials retrieved" -ForegroundColor Green
Write-Host ""

# Build and push Docker image
Write-Host "🐳 Building Docker image..." -ForegroundColor Cyan
Push-Location
try {
    Set-Location (Split-Path -Parent $PSScriptRoot)
    
    # Login to ACR
    Write-Host "   Logging in to ACR..." -ForegroundColor Yellow
    az acr login --name $AcrName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to login to ACR" -ForegroundColor Red
        exit 1
    }
    
    $fullImageName = "$acrLoginServer/${ImageName}:${ImageTag}"
    
    # Build image
    Write-Host "   Building image: $fullImageName" -ForegroundColor Yellow
    docker build -t $fullImageName -f Dockerfile .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to build Docker image" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Docker image built" -ForegroundColor Green
    
    # Push image
    Write-Host "   Pushing image to ACR..." -ForegroundColor Yellow
    docker push $fullImageName
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to push Docker image" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Docker image pushed to ACR" -ForegroundColor Green
    
} finally {
    Pop-Location
}
Write-Host ""

# Create App Service Plan if it doesn't exist
Write-Host "📋 Checking App Service Plan..." -ForegroundColor Cyan
$planExists = az appservice plan show --name $AppServicePlan --resource-group $ResourceGroupName 2>$null
if (-not $planExists) {
    Write-Host "   Creating App Service Plan: $AppServicePlan" -ForegroundColor Yellow
    az appservice plan create `
        --name $AppServicePlan `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku $Sku `
        --is-linux `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ App Service Plan created" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create App Service Plan" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ App Service Plan exists" -ForegroundColor Green
}
Write-Host ""

# Create Web App if it doesn't exist
Write-Host "🌐 Checking Web App..." -ForegroundColor Cyan
$webAppExists = az webapp show --name $AppServiceName --resource-group $ResourceGroupName 2>$null
if (-not $webAppExists) {
    Write-Host "   Creating Web App: $AppServiceName" -ForegroundColor Yellow
    az webapp create `
        --name $AppServiceName `
        --resource-group $ResourceGroupName `
        --plan $AppServicePlan `
        --deployment-container-image-name "$acrLoginServer/${ImageName}:${ImageTag}" `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Web App created" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create Web App" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ Web App exists" -ForegroundColor Green
}
Write-Host ""

# Configure ACR credentials for the Web App
Write-Host "🔐 Configuring ACR credentials..." -ForegroundColor Cyan
az webapp config container set `
    --name $AppServiceName `
    --resource-group $ResourceGroupName `
    --docker-custom-image-name "$acrLoginServer/${ImageName}:${ImageTag}" `
    --docker-registry-server-url "https://$acrLoginServer" `
    --docker-registry-server-user $acrCredentials.username `
    --docker-registry-server-password $acrCredentials.passwords[0].value `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ ACR credentials configured" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to configure ACR credentials" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Load environment variables from .env file
Write-Host "📋 Loading environment variables from .env..." -ForegroundColor Cyan
$envVars = @()
Get-Content $EnvFilePath | ForEach-Object {
    $line = $_.Trim()
    # Skip comments and empty lines
    if ($line -and -not $line.StartsWith('#')) {
        # Parse KEY=VALUE format
        if ($line -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            
            # Remove surrounding quotes if present
            if ($value -match '^"(.*)"$' -or $value -match "^'(.*)'$") {
                $value = $matches[1]
            }
            
            # Add to environment variables array
            $envVars += "$key=$value"
            Write-Host "   ✓ $key" -ForegroundColor Gray
        }
    }
}

Write-Host "✅ Found $($envVars.Count) environment variables" -ForegroundColor Green
Write-Host ""

# Set environment variables in App Service
Write-Host "⚙️  Configuring App Service environment variables..." -ForegroundColor Cyan
if ($envVars.Count -gt 0) {
    az webapp config appsettings set `
        --name $AppServiceName `
        --resource-group $ResourceGroupName `
        --settings @envVars `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Environment variables configured" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to configure environment variables" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "⚠️  No environment variables found in .env file" -ForegroundColor Yellow
}
Write-Host ""

# Enable continuous deployment (webhook for ACR)
Write-Host "⚙️  Enabling continuous deployment..." -ForegroundColor Cyan
az webapp deployment container config `
    --name $AppServiceName `
    --resource-group $ResourceGroupName `
    --enable-cd true `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Continuous deployment enabled" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Failed to enable continuous deployment" -ForegroundColor Yellow
}
Write-Host ""

# Restart the web app to pull the latest image
Write-Host "🔄 Restarting Web App..." -ForegroundColor Cyan
az webapp restart --name $AppServiceName --resource-group $ResourceGroupName --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Web App restarted" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Failed to restart Web App" -ForegroundColor Yellow
}
Write-Host ""

# Get the app URL
$appUrl = "https://$AppServiceName.azurewebsites.net"
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Application URL: $appUrl" -ForegroundColor White
Write-Host "📊 Health Check: $appUrl/health" -ForegroundColor White
Write-Host "📖 API Docs: $appUrl/docs" -ForegroundColor White
Write-Host "🐳 Container Image: $acrLoginServer/${ImageName}:${ImageTag}" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "   View logs:" -ForegroundColor White
Write-Host "   az webapp log tail --name $AppServiceName --resource-group $ResourceGroupName" -ForegroundColor Gray
Write-Host ""
Write-Host "   Restart app:" -ForegroundColor White
Write-Host "   az webapp restart --name $AppServiceName --resource-group $ResourceGroupName" -ForegroundColor Gray
Write-Host ""
Write-Host "   View container settings:" -ForegroundColor White
Write-Host "   az webapp config container show --name $AppServiceName --resource-group $ResourceGroupName" -ForegroundColor Gray
Write-Host ""
Write-Host "   Rebuild and redeploy:" -ForegroundColor White
Write-Host "   .\deploy-api.ps1 -ResourceGroupName $ResourceGroupName -AppServiceName $AppServiceName -AcrName $AcrName" -ForegroundColor Gray
Write-Host ""
