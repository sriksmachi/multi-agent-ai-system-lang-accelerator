# Multi-Agent System Deployment Guide

## Architecture Overview

This system deploys each agent as an independent container using FastAPI and connects them via A2A (Agent-to-Agent) protocol over HTTP.

### Services Architecture

```
Internet → Azure Front Door (optional)
    ↓
Orchestrator API (external, port 8000)
    ↓ (internal A2A protocol)
    ├─→ Planner Agent (internal, port 8001)
    ├─→ Researcher Agent (internal, port 8002)
    ├─→ Writer Agent (internal, port 8003)
    └─→ Reviewer Agent (internal, port 8004)
```

### Service Ports

- **Orchestrator API**: 8000 (external)
- **Planner Agent**: 8001 (internal only)
- **Researcher Agent**: 8002 (internal only)
- **Writer Agent**: 8003 (internal only)
- **Reviewer Agent**: 8004 (internal only)

## Local Development with Docker Compose

### Prerequisites

- Docker Desktop installed and running
- `.env` file configured with Azure service credentials

### Setup

1. **Copy environment template:**
   ```powershell
   Copy-Item .env.param .env
   ```

2. **Configure `.env` file** with your Azure credentials:
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_DEPLOYMENT_NAME`
   - `AZURE_SEARCH_ENDPOINT`
   - `AZURE_SEARCH_ADMIN_KEY`
   - `AZURE_COSMOSDB_ENDPOINT`
   - `AZURE_COSMOSDB_KEY`

3. **Start all services:**
   ```powershell
   docker-compose up --build
   ```

4. **Verify services are running:**
   ```powershell
   # Check all containers
   docker-compose ps
   
   # Test health endpoints
   curl http://localhost:8001/health  # Planner
   curl http://localhost:8002/health  # Researcher
   curl http://localhost:8003/health  # Writer
   curl http://localhost:8004/health  # Reviewer
   curl http://localhost:8000/health  # Orchestrator
   ```

5. **View logs:**
   ```powershell
   # All services
   docker-compose logs -f
   
   # Specific service
   docker-compose logs -f planner
   docker-compose logs -f researcher
   docker-compose logs -f writer
   docker-compose logs -f reviewer
   docker-compose logs -f orchestrator
   ```

6. **Stop services:**
   ```powershell
   docker-compose down
   ```

## Azure Container Apps Deployment

### Prerequisites

- Azure subscription
- Azure CLI installed
- Azure Developer CLI (azd) installed
- Bicep CLI installed

### Deployment Steps

#### 1. Login to Azure

```powershell
az login
azd auth login
```

#### 2. Initialize Azure Developer CLI

```powershell
azd init
```

#### 3. Provision Infrastructure

```powershell
# This creates all Azure resources defined in infra/
azd provision
```

This will create:
- ✅ Container Apps Environment
- ✅ Container Registry
- ✅ 4 Agent Container Apps (Planner, Researcher, Writer, Reviewer)
- ✅ 1 Orchestrator API Container App
- ✅ Azure OpenAI
- ✅ Azure AI Search
- ✅ Azure Cosmos DB
- ✅ Application Insights
- ✅ Log Analytics Workspace

#### 4. Build and Push Container Images

```powershell
# Get registry name from outputs
$REGISTRY_NAME = azd env get-values | Select-String "CONTAINER_REGISTRY_NAME" | ForEach-Object { $_ -replace '.*=', '' }

# Build and push each agent
az acr build --registry $REGISTRY_NAME --image planner-agent:latest -f agents/planner_agent/Dockerfile .
az acr build --registry $REGISTRY_NAME --image researcher-agent:latest -f agents/researcher_agent/Dockerfile .
az acr build --registry $REGISTRY_NAME --image writer-agent:latest -f agents/writer_agent/Dockerfile .
az acr build --registry $REGISTRY_NAME --image reviewer-agent:latest -f agents/reviewer_agent/Dockerfile .
az acr build --registry $REGISTRY_NAME --image orchestrator-api:latest -f Dockerfile .
```

#### 5. Update Container Apps with Images

```powershell
# Get resource group
$RESOURCE_GROUP = azd env get-values | Select-String "AZURE_RESOURCE_GROUP" | ForEach-Object { $_ -replace '.*=', '' }
$REGISTRY_SERVER = "$REGISTRY_NAME.azurecr.io"

# Update each container app
az containerapp update `
  --name ca-planner-* `
  --resource-group $RESOURCE_GROUP `
  --image "$REGISTRY_SERVER/planner-agent:latest"

az containerapp update `
  --name ca-researcher-* `
  --resource-group $RESOURCE_GROUP `
  --image "$REGISTRY_SERVER/researcher-agent:latest"

az containerapp update `
  --name ca-writer-* `
  --resource-group $RESOURCE_GROUP `
  --image "$REGISTRY_SERVER/writer-agent:latest"

az containerapp update `
  --name ca-reviewer-* `
  --resource-group $RESOURCE_GROUP `
  --image "$REGISTRY_SERVER/reviewer-agent:latest"

az containerapp update `
  --name ca-orchestrator-* `
  --resource-group $RESOURCE_GROUP `
  --image "$REGISTRY_SERVER/orchestrator-api:latest"
```

#### 6. Verify Deployment

```powershell
# Get orchestrator URL
$ORCHESTRATOR_URL = az containerapp show `
  --name ca-orchestrator-* `
  --resource-group $RESOURCE_GROUP `
  --query "properties.configuration.ingress.fqdn" -o tsv

# Test the API
curl "https://$ORCHESTRATOR_URL/health"
```

### Alternative: One-Command Deployment

Use the provided deployment script:

```powershell
.\infra\deploy-all.ps1
```

## Monitoring and Observability

### Application Insights

All services are instrumented with OpenTelemetry and send telemetry to Application Insights:

1. **Navigate to Application Insights** in Azure Portal
2. **View Application Map** to see service dependencies
3. **Monitor Performance** to view request durations
4. **Check Failures** for error tracking
5. **View Distributed Traces** for end-to-end request flows

### Container Apps Logs

```powershell
# Stream logs from a specific agent
az containerapp logs show `
  --name ca-planner-* `
  --resource-group $RESOURCE_GROUP `
  --follow

# View metrics
az monitor metrics list `
  --resource /subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.App/containerApps/ca-planner-* `
  --metric Requests
```

### Log Analytics Queries

```kql
// View all agent requests
ContainerAppConsoleLogs_CL
| where ContainerAppName_s startswith "ca-"
| where Log_s contains "Agent"
| project TimeGenerated, ContainerAppName_s, Log_s
| order by TimeGenerated desc

// Track request flow through agents
AppTraces
| where Message contains "thread_id"
| project timestamp, Message, AppRoleName
| order by timestamp asc
```

## Scaling Configuration

### Auto-scaling Rules

Each agent is configured to scale based on HTTP requests:

```bicep
scale: {
  minReplicas: 1
  maxReplicas: 10
  rules: [
    {
      name: 'http-scaling'
      http: {
        metadata: {
          concurrentRequests: '10'
        }
      }
    }
  ]
}
```

### Manual Scaling

```powershell
# Scale a specific agent
az containerapp update `
  --name ca-planner-* `
  --resource-group $RESOURCE_GROUP `
  --min-replicas 2 `
  --max-replicas 20
```

## Troubleshooting

### Service Not Responding

1. **Check health endpoint:**
   ```powershell
   curl https://<agent-fqdn>/health
   ```

2. **View container logs:**
   ```powershell
   az containerapp logs show --name <app-name> --resource-group <rg> --follow
   ```

3. **Check revision status:**
   ```powershell
   az containerapp revision list --name <app-name> --resource-group <rg>
   ```

### Agent Communication Failures

1. **Verify internal URLs** in orchestrator environment variables
2. **Check Application Insights** for dependency failures
3. **Verify network configuration** in Container Apps Environment

### High Latency

1. **Review Application Insights Performance blade**
2. **Check agent resource allocation** (CPU/Memory)
3. **Verify Azure OpenAI throttling limits**
4. **Scale up agent replicas** if needed

## Cost Optimization

### Development Environment

- Use **consumption tier** for Container Apps
- Set `minReplicas: 0` to scale to zero when idle
- Use **Basic SKU** for Container Registry
- Use **Basic SKU** for AI Search

### Production Environment

- Use **Dedicated tier** for Container Apps for better performance
- Set appropriate `minReplicas` based on expected load
- Use **Standard SKU** for Container Registry with geo-replication
- Use **Standard SKU** for AI Search with replicas

## Security Best Practices

1. **Managed Identity**: All services use managed identity for Azure service authentication
2. **Internal Networking**: Agent services are not exposed externally
3. **Secret Management**: Sensitive values stored in Container Apps secrets
4. **HTTPS Only**: All communication uses HTTPS
5. **RBAC**: Principle of least privilege for role assignments

## Next Steps

- [ ] Configure custom domain for orchestrator API
- [ ] Set up CI/CD pipeline for automated deployments
- [ ] Configure Azure Front Door for global distribution
- [ ] Implement API authentication (OAuth/API Keys)
- [ ] Set up backup and disaster recovery
- [ ] Configure monitoring alerts and dashboards
