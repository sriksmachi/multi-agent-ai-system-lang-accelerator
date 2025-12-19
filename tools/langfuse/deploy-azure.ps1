# Langfuse Deployment Script for Azure App Service with SQLite
# Simplified script with hardcoded resource names

# Hardcoded resource names
$ResourceGroup = "rg-langfuse"
$Location = "eastus"
$AcrName = "acrlangfuse5497"
$AppServicePlan = "plan-langfuse"
$AppService = "langfuse-sriks"
$StorageAccount = "stlangfuse3594"
$AppServiceSku = "S1"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "Langfuse Deployment to Azure App Service" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Azure CLI is installed
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed. Please install it first." -ForegroundColor Red
    Write-Host "   Download from: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    exit 1
}

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Display configuration
Write-Host "📋 Deployment Configuration:" -ForegroundColor Cyan
Write-Host "   Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "   Location: $Location" -ForegroundColor White
Write-Host "   App Service SKU: $AppServiceSku" -ForegroundColor White

# Generate secrets
Write-Host "🔐 Generating secure secrets..." -ForegroundColor Cyan
$NEXTAUTH_SECRET = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$SALT = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
Write-Host "✅ Secrets generated" -ForegroundColor Green
Write-Host ""

Write-Host "ℹ️  Using existing Azure resources..." -ForegroundColor Yellow
Write-Host ""

# Get storage account key
Write-Host "🔑 Retrieving storage account key..." -ForegroundColor Cyan
$STORAGE_KEY = az storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --query "[0].value" `
    --output tsv
Write-Host "✅ Storage key retrieved" -ForegroundColor Green
Write-Host ""

# Build and push Docker image
Write-Host "🔨 Building and pushing Docker image..." -ForegroundColor Cyan
az acr login --name $AcrName
$ACR_LOGIN_SERVER = az acr show --name $AcrName --query loginServer --output tsv

Push-Location $PSScriptRoot
docker build -t "${ACR_LOGIN_SERVER}/langfuse:latest" -f dockerfile .
if ($LASTEXITCODE -eq 0) {
    docker push "${ACR_LOGIN_SERVER}/langfuse:latest"
    Write-Host "✅ Docker image built and pushed" -ForegroundColor Green
} else {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host ""

# Get ACR credentials
$ACR_USERNAME = az acr credential show --name $AcrName --query username --output tsv
$ACR_PASSWORD = az acr credential show --name $AcrName --query "passwords[0].value" --output tsv

# Configure container registry credentials
Write-Host "🔐 Updating container configuration..." -ForegroundColor Cyan
az webapp config container set `
    --resource-group $ResourceGroup `
    --name $AppService `
    --container-image-name "${ACR_LOGIN_SERVER}/langfuse:latest" `
    --container-registry-url "https://${ACR_LOGIN_SERVER}" `
    --container-registry-user $ACR_USERNAME `
    --container-registry-password $ACR_PASSWORD `
    --output none

Write-Host "✅ Container configuration updated" -ForegroundColor Green
Write-Host ""

# Build DATABASE_URL for PostgreSQL
# Update the username and password below with your actual credentials
$PostgresUser = "your_postgres_username"
$PostgresPassword = "your_postgres_password"  # Replace with your actual password
$PostgresHost = "your-postgres-server.postgres.database.azure.com"
$PostgresDatabase = "langfuse"

$DATABASE_URL = "postgresql://${PostgresUser}:${PostgresPassword}@${PostgresHost}:5432/${PostgresDatabase}?sslmode=require"

Write-Host "📊 Using PostgreSQL database: $PostgresHost" -ForegroundColor Cyan
Write-Host ""

# Azure Blob Storage configuration for event uploads
$BlobAccountName = $StorageAccount
$BlobAccountKey = ""
$BlobEndpoint = "https://${BlobAccountName}.blob.core.windows.net"
$BlobContainer = "langfuse"

Write-Host "📦 Using Azure Blob Storage: $BlobAccountName" -ForegroundColor Cyan
Write-Host ""

# Configure App Settings
Write-Host "⚙️  Configuring application settings..." -ForegroundColor Cyan
az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $AppService `
    --settings `
        DATABASE_URL=$DATABASE_URL `
        NEXTAUTH_URL="https://${AppService}.azurewebsites.net" `
        NEXTAUTH_SECRET=$NEXTAUTH_SECRET `
        SALT=$SALT `
        TELEMETRY_ENABLED=1 `
        LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES="false" `
        LANGFUSE_CLICKHOUSE_ENABLED="false" `
        CLICKHOUSE_CLUSTER_ENABLED="false" `
        LANGFUSE_AUTO_CLICKHOUSE_MIGRATION_DISABLED="true" `
        LANGFUSE_USE_AZURE_BLOB="true" `
        LANGFUSE_S3_EVENT_UPLOAD_BUCKET=$BlobContainer `
        LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=$BlobAccountName `
        LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=$BlobAccountKey `
        LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=$BlobEndpoint `
        WEBSITES_PORT=8000 `
        PORT=8000 `
    --output none
Write-Host "✅ Application settings configured" -ForegroundColor Green
Write-Host ""

# Enable logging
Write-Host "📝 Enabling application logging..." -ForegroundColor Cyan
az webapp log config `
    --resource-group $ResourceGroup `
    --name $AppService `
    --application-logging filesystem `
    --detailed-error-messages true `
    --failed-request-tracing true `
    --web-server-logging filesystem `
    --output none
Write-Host "✅ Logging enabled" -ForegroundColor Green
Write-Host ""

# Restart the web app to apply changes
Write-Host "🔄 Restarting web app..." -ForegroundColor Cyan
az webapp restart --resource-group $ResourceGroup --name $AppService --output none
Write-Host "✅ Web app restarted" -ForegroundColor Green
Write-Host ""

# Wait a moment for the container to start
Write-Host "⏳ Waiting for container to start (30 seconds)..." -ForegroundColor Cyan
Start-Sleep -Seconds 30