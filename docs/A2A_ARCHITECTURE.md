# A2A Multi-Agent Architecture Implementation

## Overview

This implementation transforms the multi-agent system into a distributed microservices architecture where each agent runs as an independent FastAPI service, communicating via the A2A (Agent-to-Agent) protocol over HTTP.

## What Changed

### 🆕 New Files Created

#### Core Protocol
- **`core/a2a_protocol.py`** - A2A protocol definitions (request/response models)

#### Agent Services (4 new microservices)
Each agent now has:
- **`agents/*/main.py`** - FastAPI service entry point
- **`agents/*/schemas.py`** - Request/response schemas
- **`agents/*/Dockerfile`** - Container build configuration
- **`agents/*/requirements.txt`** - Python dependencies

Agents created:
1. **Planner Agent** (port 8001)
2. **Researcher Agent** (port 8002)
3. **Writer Agent** (port 8003)
4. **Reviewer Agent** (port 8004)

#### Orchestration
- **`workflows/agent_orchestrator.py`** - HTTP-based orchestrator replacing direct function calls

#### Infrastructure
- **`infra/app/agent-planner.bicep`** - Planner Container App
- **`infra/app/agent-researcher.bicep`** - Researcher Container App
- **`infra/app/agent-writer.bicep`** - Writer Container App
- **`infra/app/agent-reviewer.bicep`** - Reviewer Container App

#### Deployment
- **`docker-compose.yml`** - Local multi-container orchestration
- **`docs/DEPLOYMENT_GUIDE.md`** - Comprehensive deployment guide
- **`infra/deploy-all.ps1`** - Automated Azure deployment script

### 🔄 Modified Files

#### Infrastructure
- **`infra/resources.bicep`** - Added 4 agent container apps + updated orchestrator
- **`infra/app/api.bicep`** - Added agent service URLs and Cosmos DB configuration
- **`.env.param`** - Added agent service URLs and ports

## Architecture Changes

### Before (Monolithic)
```
┌─────────────────────────────────┐
│   Single API Container          │
│  ┌──────────┐  ┌──────────┐   │
│  │ Planner  │  │Researcher│   │
│  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐   │
│  │  Writer  │  │ Reviewer │   │
│  └──────────┘  └──────────┘   │
└─────────────────────────────────┘
```

### After (Microservices with A2A Protocol)
```
┌─────────────────────────────────┐
│   Orchestrator API (8000)       │
│   External, HTTP/HTTPS          │
└────────┬────────────────────────┘
         │ A2A Protocol (HTTP)
    ┌────┴────┬─────────┬─────────┐
    │         │         │         │
┌───▼───┐ ┌──▼───┐ ┌──▼───┐ ┌───▼───┐
│Planner│ │Resear│ │Writer│ │Review │
│ 8001  │ │ 8002 │ │ 8003 │ │ 8004  │
└───────┘ └──────┘ └──────┘ └───────┘
Internal only, A2A communication
```

## Key Features

### ✅ Independent Scaling
Each agent can scale independently based on its workload:
- Planner: 1-10 replicas
- Researcher: 1-10 replicas
- Writer: 1-10 replicas
- Reviewer: 1-10 replicas

### ✅ A2A Protocol Standardization
All inter-agent communication uses standardized format:
```python
class A2ARequest:
    agent_id: str
    thread_id: str
    user_id: str
    timestamp: str
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]]

class A2AResponse:
    agent_id: str
    thread_id: str
    timestamp: str
    status: str  # success, error, partial
    result: Dict[str, Any]
    metadata: Optional[Dict[str, Any]]
```

### ✅ Fault Isolation
If one agent fails, others continue operating independently.

### ✅ Technology Flexibility
Each agent can use different:
- Programming languages (currently all Python/FastAPI)
- AI models or providers
- Scaling configurations
- Resource allocations (CPU/Memory)

### ✅ Observability
- Distributed tracing via OpenTelemetry
- Per-agent metrics in Application Insights
- Detailed logging with thread tracking
- Health check endpoints for each service

### ✅ Container Apps Native
- Internal service discovery
- Managed identity for Azure services
- Auto-scaling based on HTTP load
- Zero-downtime deployments

## Deployment Options

### Local Development (Docker Compose)
```powershell
# Copy environment file
Copy-Item .env.param .env

# Edit .env with your Azure credentials

# Start all services
docker-compose up --build

# Test
curl http://localhost:8000/health
```

### Azure Container Apps
```powershell
# Provision infrastructure
azd provision

# Deploy all services
.\infra\deploy-all.ps1

# Or deploy individually
az acr build --registry <registry> --image planner-agent:latest -f agents/planner_agent/Dockerfile .
```

See **[docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** for detailed instructions.

## Service Endpoints

### Local (Docker Compose)
- **Orchestrator**: http://localhost:8000
- **Planner**: http://localhost:8001 (internal)
- **Researcher**: http://localhost:8002 (internal)
- **Writer**: http://localhost:8003 (internal)
- **Reviewer**: http://localhost:8004 (internal)

### Azure Container Apps
- **Orchestrator**: https://ca-orchestrator-{env}.{region}.azurecontainerapps.io (external)
- **Agents**: https://ca-{agent}-{env}.internal.{region}.azurecontainerapps.io (internal only)

## API Examples

### Health Check
```bash
# Check orchestrator
curl http://localhost:8000/health

# Check individual agents
curl http://localhost:8001/health  # Planner
curl http://localhost:8002/health  # Researcher
curl http://localhost:8003/health  # Writer
curl http://localhost:8004/health  # Reviewer
```

### Generate Post (via Orchestrator)
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "artificial intelligence in healthcare",
    "user_id": "user123",
    "platform": "linkedin",
    "tone": "professional"
  }'
```

### Call Individual Agent (Direct - for testing)
```bash
# Planner
curl -X POST http://localhost:8001/plan \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "topic": "AI in healthcare",
    "platform": "linkedin",
    "tone": "professional",
    "thread_id": "test-123"
  }'

# Researcher
curl -X POST http://localhost:8002/research \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "topic": "AI in healthcare",
    "plan": "...",
    "thread_id": "test-123"
  }'
```

## Monitoring

### View Logs
```powershell
# Docker Compose
docker-compose logs -f planner
docker-compose logs -f researcher

# Azure Container Apps
az containerapp logs show --name ca-planner-{env} --resource-group {rg} --follow
```

### Application Insights
- **Application Map**: View service topology and dependencies
- **Performance**: Monitor request durations per agent
- **Failures**: Track errors across the distributed system
- **Distributed Traces**: Follow requests through the entire workflow

### Metrics
```powershell
# View agent metrics
az monitor metrics list \
  --resource /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.App/containerApps/ca-planner-{env} \
  --metric Requests
```

## Testing the Migration

### 1. Test Individual Agents
```powershell
# Start services
docker-compose up -d

# Test each agent health
$agents = @("planner", "researcher", "writer", "reviewer", "orchestrator")
foreach ($agent in $agents) {
    $port = switch ($agent) {
        "orchestrator" { 8000 }
        "planner" { 8001 }
        "researcher" { 8002 }
        "writer" { 8003 }
        "reviewer" { 8004 }
    }
    Write-Host "Testing $agent..."
    curl "http://localhost:$port/health"
}
```

### 2. Test End-to-End Workflow
```powershell
# Call orchestrator which coordinates all agents
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "cloud computing trends", "user_id": "test-user"}'
```

### 3. Monitor Distributed Traces
1. Open Application Insights in Azure Portal
2. Navigate to **Application Map**
3. Trigger a request
4. View the trace showing: Orchestrator → Planner → Researcher → Writer → Reviewer

## Benefits Achieved

✅ **Independent Scaling** - Each agent scales based on its workload  
✅ **Fault Isolation** - Agent failures don't crash the entire system  
✅ **Technology Flexibility** - Each agent can use different tech stacks  
✅ **Easier Development** - Teams can work on agents independently  
✅ **Better Observability** - Clear service boundaries and traces  
✅ **Container Apps Native** - Optimized for Azure's serverless containers  
✅ **Cost Optimization** - Scale individual agents, not entire monolith  
✅ **A2A Protocol Ready** - Standardized communication for future expansion  

## Migration Checklist

- [x] Create A2A protocol module
- [x] Create FastAPI services for each agent
- [x] Create Dockerfiles for each agent
- [x] Create HTTP-based orchestrator
- [x] Create Bicep modules for Container Apps
- [x] Update main infrastructure Bicep
- [x] Create Docker Compose for local dev
- [x] Update environment configuration
- [x] Create deployment automation scripts
- [x] Create comprehensive deployment guide

## Next Steps

1. **Update API Routes** - Modify [`api/routes/`](api/routes/) to use `AgentOrchestrator`
2. **Test Locally** - Run `docker-compose up` and verify all agents
3. **Deploy to Azure** - Run `azd provision` then `.\infra\deploy-all.ps1`
4. **Monitor** - Check Application Insights for traces
5. **Optimize** - Adjust scaling rules based on production load
6. **Secure** - Add authentication/authorization between services

## Resources

- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Complete deployment instructions
- **[Docker Compose](docker-compose.yml)** - Local development configuration
- **[Bicep Infrastructure](infra/)** - Azure infrastructure as code
- **[A2A Protocol](core/a2a_protocol.py)** - Communication protocol specification
