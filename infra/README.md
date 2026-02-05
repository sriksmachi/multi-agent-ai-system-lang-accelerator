# Infrastructure Deployment Guide

This directory contains Bicep templates for deploying the Multi-Agent AI System infrastructure to Azure.

## Overview

The infrastructure deployment creates the following Azure resources:

### Core Services
- **Azure OpenAI** - GPT-4o model with chat and embeddings deployments
- **Azure Cosmos DB** - Serverless database for conversation checkpointing
- **Azure AI Search** - Vector search and document retrieval
- **Application Insights** - Distributed tracing and monitoring
- **Storage Account** - Blob storage for data and artifacts

### Deployment Services
- **Container Registry** - Docker image repository
- **Container Apps Environment** - Serverless container hosting
- **Container App** - API service deployment
- **Log Analytics Workspace** - Centralized logging

### AI Platform
- **AI Hub** - Azure AI Foundry hub
- **AI Project** - Azure AI Foundry project
- **Key Vault** - Secrets management

## Prerequisites

1. **Azure CLI** - [Install Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
2. **Azure Subscription** - Active Azure subscription with Owner or Contributor access
3. **Azure Developer CLI (azd)** - Optional but recommended: [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)

## Deployment Options

### Option 1: Using Azure Developer CLI (Recommended)

```bash
# Login to Azure
azd auth login

# Initialize the project (first time only)
azd init

# Provision infrastructure
azd provision

# Deploy the application
azd deploy
```

The `azd` command automatically:
- Creates the resource group
- Deploys all Bicep templates
- Sets up environment variables
- Builds and deploys the container

### Option 2: Using Azure CLI with Bicep

#### Step 1: Login to Azure

```bash
az login
az account set --subscription "<your-subscription-id>"
```

#### Step 2: Set Deployment Parameters

Edit `main.parameters.json` or create a new parameters file:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environmentName": {
      "value": "myenv"
    },
    "location": {
      "value": "eastus"
    },
    "principalId": {
      "value": "<your-user-object-id>"
    }
  }
}
```

Get your principal ID:
```bash
az ad signed-in-user show --query id -o tsv
```

#### Step 3: Deploy Infrastructure

```bash
# Navigate to infra directory
cd infra

# Deploy at subscription scope
az deployment sub create \
  --name multi-agent-deployment \
  --location eastus \
  --template-file main.bicep \
  --parameters main.parameters.json
```

#### Step 4: Get Deployment Outputs

```bash
# Get all outputs
az deployment sub show \
  --name multi-agent-deployment \
  --query properties.outputs

# Get specific output
az deployment sub show \
  --name multi-agent-deployment \
  --query properties.outputs.AZURE_OPENAI_API_KEY.value -o tsv
```

#### Step 5: Create .env File

Create a `.env` file in the root directory with the deployment outputs:

```bash
# Generate .env from deployment outputs
cat > ../.env << EOF
AZURE_OPENAI_ENDPOINT=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_ENDPOINT.value -o tsv)
AZURE_OPENAI_API_KEY=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_API_KEY.value -o tsv)
AZURE_OPENAI_DEPLOYMENT_NAME=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_DEPLOYMENT_NAME.value -o tsv)
AZURE_OPENAI_API_VERSION=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_API_VERSION.value -o tsv)
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT.value -o tsv)
AZURE_OPENAI_EMBEDDINGS_ENDPOINT=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_EMBEDDINGS_ENDPOINT.value -o tsv)
AZURE_OPENAI_EMBEDDINGS_API_KEY=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_EMBEDDINGS_API_KEY.value -o tsv)
AZURE_OPENAI_EMBEDDINGS_API_VERSION=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_OPENAI_EMBEDDINGS_API_VERSION.value -o tsv)
COSMOS_ENDPOINT=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.COSMOS_ENDPOINT.value -o tsv)
COSMOS_PRIMARY_KEY=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.COSMOS_PRIMARY_KEY.value -o tsv)
COSMOS_DATABASE_NAME=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.COSMOS_DATABASE_NAME.value -o tsv)
COSMOS_CHECKPOINTS_CONTAINER=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.COSMOS_CHECKPOINTS_CONTAINER.value -o tsv)
AZURE_SEARCH_ENDPOINT=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_SEARCH_ENDPOINT.value -o tsv)
AZURE_SEARCH_ADMIN_KEY=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_SEARCH_ADMIN_KEY.value -o tsv)
AZURE_SEARCH_INDEX_NAME=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.AZURE_SEARCH_INDEX_NAME.value -o tsv)
APPLICATIONINSIGHTS_CONNECTION_STRING=$(az deployment sub show --name multi-agent-deployment --query properties.outputs.APPLICATIONINSIGHTS_CONNECTION_STRING.value -o tsv)
CHECKPOINTER=cosmos
USE_MANAGED_IDENTITY=false
EOF
```

### Option 3: Using PowerShell Deployment Script

```powershell
# Run the provided deployment script
.\deploy-api.ps1
```

## Post-Deployment Steps

### 1. Create Search Index

After deployment, create the search index for document retrieval:

```bash
cd datapipeline
python create_search_index.py
```

### 2. Ingest Documents (Optional)

If you have documents to ingest:

```bash
# Place PDFs in data/papers directory
python run_datapipeline.py
```

### 3. Run the Application Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API server
python api/main.py
```

The API will start at `http://localhost:8000` with the MCP endpoint at `/mcp`.

### 4. Test the Deployment

```bash
# Test with MCP client
cd clients
python mcp_client.py
```

Or use MCP Inspector:
```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

## Resource Naming Convention

Resources are named using the following pattern:
- **Resource Group**: `rg-{environmentName}`
- **Storage Account**: `st{environmentName}{uniqueString}`
- **Azure OpenAI**: `oai-{environmentName}`
- **Cosmos DB**: `cosmos-{environmentName}{uniqueString}`
- **AI Search**: `srch-{environmentName}`
- **Container Registry**: `cr{environmentName}{uniqueString}`
- **Key Vault**: `kv-{environmentName}{uniqueString}`
- **Container App**: `ca-api-{environmentName}`

## Cost Optimization

The deployment uses cost-effective tiers by default:
- **Azure OpenAI**: Standard tier, 50 TPM capacity
- **Cosmos DB**: Serverless (pay-per-request)
- **AI Search**: Basic tier
- **Storage**: Standard LRS
- **Container Registry**: Basic tier

## Cleanup

To delete all resources:

```bash
# Using Azure CLI
az group delete --name rg-{environmentName} --yes --no-wait

# Using azd
azd down
```

## Troubleshooting

### Deployment Failures

**Issue**: OpenAI deployment fails
- **Solution**: Check regional availability. Try different regions: `eastus`, `swedencentral`, `francecentral`

**Issue**: Insufficient quota for OpenAI
- **Solution**: Request quota increase in Azure Portal > Azure OpenAI > Quotas

**Issue**: Role assignment fails
- **Solution**: Ensure you have Owner or User Access Administrator role on the subscription

### Application Issues

**Issue**: Cannot connect to Cosmos DB
- **Solution**: Check firewall settings. Enable "Allow access from Azure services" in Cosmos DB

**Issue**: Search index not found
- **Solution**: Run `python datapipeline/create_search_index.py` to create the index

## Additional Resources

- [Azure Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure Cosmos DB](https://learn.microsoft.com/azure/cosmos-db/)
- [Azure AI Search](https://learn.microsoft.com/azure/search/)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
