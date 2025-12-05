# Deploying Langfuse to Azure App Service

This directory contains the Dockerfile and configuration for deploying Langfuse to Azure App Service.

## Quick Start

### Automated Deployment (Recommended)

```powershell
cd tools/langfuse

# Default deployment with S1 SKU (better quota availability)
.\deploy-azure.ps1

# Or specify SKU if you have quota for Basic tier
.\deploy-azure.ps1 -AppServiceSku B1

# Or use a different region
.\deploy-azure.ps1 -AppServiceSku S1 -Location westus2
```

### Quota Issues?

If you encounter quota limit errors, see [TROUBLESHOOTING-QUOTA.md](./TROUBLESHOOTING-QUOTA.md) for solutions.

**Quick fix**: Use S1 SKU instead of B1:
```powershell
.\deploy-azure.ps1 -AppServiceSku S1
```

## Prerequisites

1. **Azure Container Registry (ACR)** - to store the Docker image
2. **Azure Storage Account** - for SQLite database persistence
3. **Azure App Service (Linux)** - to run the container

## Environment Variables Required

Configure these in Azure App Service → Configuration → Application Settings:

```bash
# Database (SQLite)
DATABASE_URL=file:/var/lib/langfuse/langfuse.db

# NextAuth Configuration (Required)
NEXTAUTH_URL=https://your-app-name.azurewebsites.net
NEXTAUTH_SECRET=your-random-secret-key-min-32-chars

# Salt for API keys (Required)
SALT=your-random-salt-min-32-chars

# Telemetry (Optional - set to 1 to disable)
TELEMETRY_ENABLED=0

# Authentication (Optional)
# Enable if you want to disable signups
# AUTH_DISABLE_SIGNUP=true

# SSO Configuration (Optional)
# AZURE_AD_CLIENT_ID=your-client-id
# AZURE_AD_CLIENT_SECRET=your-client-secret
# AZURE_AD_TENANT_ID=your-tenant-id
```

## Deployment Steps

### Step 1: Create Azure Resources

```powershell
# Set variables
$RESOURCE_GROUP="rg-langfuse"
$LOCATION="eastus"
$ACR_NAME="acrlangfuse"
$STORAGE_ACCOUNT="stlangfuse"
$APP_SERVICE_PLAN="asp-langfuse"
$APP_SERVICE="app-langfuse"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create Azure Container Registry
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true

# Create Storage Account for SQLite persistence
az storage account create `
  --resource-group $RESOURCE_GROUP `
  --name $STORAGE_ACCOUNT `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2

# Get storage account key
$STORAGE_KEY = az storage account keys list `
  --resource-group $RESOURCE_GROUP `
  --account-name $STORAGE_ACCOUNT `
  --query "[0].value" `
  --output tsv

# Create file share for SQLite database
az storage share create `
  --name "langfuse-data" `
  --account-name $STORAGE_ACCOUNT `
  --account-key $STORAGE_KEY `
  --quota 10
```

### Step 2: Build and Push Docker Image

```powershell
# Login to ACR
az acr login --name $ACR_NAME

# Get ACR login server
$ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer --output tsv

# Build and push the image
cd tools/langfuse
docker build -t ${ACR_LOGIN_SERVER}/langfuse:latest .
docker push ${ACR_LOGIN_SERVER}/langfuse:latest
```

### Step 3: Create App Service

```powershell
# Create App Service Plan (Linux)
az appservice plan create `
  --name $APP_SERVICE_PLAN `
  --resource-group $RESOURCE_GROUP `
  --is-linux `
  --sku B1

# Get ACR credentials
$ACR_USERNAME = az acr credential show --name $ACR_NAME --query username --output tsv
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" --output tsv

# Create Web App
az webapp create `
  --resource-group $RESOURCE_GROUP `
  --plan $APP_SERVICE_PLAN `
  --name $APP_SERVICE `
  --deployment-container-image-name ${ACR_LOGIN_SERVER}/langfuse:latest `
  --docker-registry-server-url "https://${ACR_LOGIN_SERVER}" `
  --docker-registry-server-user $ACR_USERNAME `
  --docker-registry-server-password $ACR_PASSWORD

# Mount Azure File Share for SQLite database
az webapp config storage-account add `
  --resource-group $RESOURCE_GROUP `
  --name $APP_SERVICE `
  --custom-id "langfusedata" `
  --storage-type AzureFiles `
  --share-name "langfuse-data" `
  --account-name $STORAGE_ACCOUNT `
  --access-key $STORAGE_KEY `
  --mount-path "/var/lib/langfuse"
```

### Step 4: Configure Environment Variables

```powershell
# Generate secrets (PowerShell)
$NEXTAUTH_SECRET = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
$SALT = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})

# Build DATABASE_URL for SQLite
$DATABASE_URL = "file:/var/lib/langfuse/langfuse.db"

# Configure app settings
az webapp config appsettings set `
  --resource-group $RESOURCE_GROUP `
  --name $APP_SERVICE `
  --settings `
    DATABASE_URL=$DATABASE_URL `
    NEXTAUTH_URL="https://${APP_SERVICE}.azurewebsites.net" `
    NEXTAUTH_SECRET=$NEXTAUTH_SECRET `
    SALT=$SALT `
    TELEMETRY_ENABLED=0 `
    WEBSITES_PORT=8000 `
    PORT=8000
```

### Step 5: Initialize Database

The first time Langfuse starts, it will automatically run database migrations. Monitor the logs:

```powershell
az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_SERVICE
```

### Step 6: Access Langfuse

Open your browser to:
```
https://${APP_SERVICE}.azurewebsites.net
```

Default login (first user becomes admin):
- Create your account through the UI

## Updating Langfuse

To update to a newer version:

```powershell
# Pull latest Langfuse image
docker pull langfuse/langfuse:latest

# Rebuild and push
cd tools/langfuse
docker build -t ${ACR_LOGIN_SERVER}/langfuse:latest .
docker push ${ACR_LOGIN_SERVER}/langfuse:latest

# Restart the web app
az webapp restart --resource-group $RESOURCE_GROUP --name $APP_SERVICE
```

## Troubleshooting

### Check Application Logs
```powershell
az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_SERVICE
```

### Enable Advanced Logging
```powershell
az webapp log config `
  --resource-group $RESOURCE_GROUP `
  --name $APP_SERVICE `
  --application-logging filesystem `
  --detailed-error-messages true `
  --failed-request-tracing true `
  --web-server-logging filesystem
```

### Common Issues

1. **Database Connection Failed**
   - Verify DATABASE_URL points to the correct SQLite path
   - Check that the Azure File Share is properly mounted
   - Verify the mount path is `/var/lib/langfuse`

2. **Application Won't Start**
   - Check NEXTAUTH_URL matches your app URL
   - Verify NEXTAUTH_SECRET and SALT are at least 32 characters
   - Check logs for specific errors

3. **Port Issues**
   - Ensure WEBSITES_PORT and PORT are both set to 8000
   - The health check endpoint should be accessible

4. **Database File Permissions**
   - SQLite requires write permissions to the database file
   - Ensure the Azure File Share has correct permissions
   - Check App Service has access to the storage account

## Security Best Practices

1. **Use Managed Identity**: Configure ACR to use managed identity instead of admin credentials
2. **Key Vault**: Store secrets in Azure Key Vault and reference them
3. **Private Endpoint**: Use private endpoints for Storage Account
4. **SSL/TLS**: App Service provides free SSL certificates
5. **Authentication**: Enable Azure AD SSO for production use
6. **Backup**: Regularly backup the SQLite database from Azure File Share

## Cost Optimization

- Use **B1 tier** for App Service Plan (~$13/month)
- Use **Standard_LRS** for Storage Account (~$0.05/month for 10GB)
- Use **Basic tier ACR** (~$5/month)

Total: ~$18/month for a basic Langfuse deployment with SQLite

## Production Recommendations

1. **Scale Up**: Use P1V2 or higher for App Service for better performance
2. **Database Backups**: Set up automated backups of the SQLite file share
3. **Monitoring**: Set up Application Insights
4. **Custom Domain**: Configure custom domain with SSL
5. **Consider PostgreSQL**: For production workloads with high concurrency, consider using PostgreSQL instead of SQLite

## Support

- Langfuse Documentation: https://langfuse.com/docs
- Azure App Service: https://docs.microsoft.com/azure/app-service/
