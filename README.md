# Multi-Agent AI System - LangGraph Accelerator

A production-ready solution accelerator for building scalable, observable, and reliable multi-agent AI systems using LangGraph, FastMCP (Model Context Protocol), and Azure services.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Purpose & Objectives](#2-purpose--objectives)
3. [Prerequisites](#3-prerequisites)
4. [How to Run](#4-how-to-run)
5. [Design](#5-design)
6. [Data Pipeline](#6-data-pipeline)
7. [Local vs Azure Deployment](#7-local-vs-azure-deployment)
8. [How to Undeploy/Delete](#8-how-to-undeploydelete)
9. [Limitations](#9-limitations)
10. [Summary](#10-summary)

---

## 1. Introduction

This repository provides a **solution accelerator** for building enterprise-grade multi-agent AI systems. It demonstrates best practices for orchestrating multiple specialized AI agents that collaborate to complete complex tasks—in this case, generating high-quality social media content.

The system implements:
- **A2A (Agent-to-Agent) Protocol** for standardized inter-agent communication
- **FastMCP (Model Context Protocol)** for exposing AI capabilities as tools
- **LangGraph** for workflow orchestration and state management
- **OpenTelemetry** for distributed tracing and observability
- **Azure Container Apps** for scalable microservices deployment

### Key Technologies

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Primary language |
| LangGraph | Workflow orchestration |
| FastAPI | REST API framework |
| FastMCP | MCP protocol server |
| Azure OpenAI | LLM inference |
| Azure AI Search | Vector search & RAG |
| Azure Cosmos DB | State checkpointing |
| Azure Container Apps | Serverless containers |
| OpenTelemetry | Distributed tracing |
| DeepEval | LLM output evaluation |

---

## 2. Purpose & Objectives

### Purpose

This accelerator serves as a **template and reference implementation** for teams building production multi-agent AI systems. It demonstrates:

1. **Microservices Architecture** - Each agent runs as an independent service
2. **A2A Protocol Communication** - Standardized HTTP-based agent communication
3. **MCP Integration** - Standards-compliant AI tool exposure
4. **RAG Pattern** - Retrieval-Augmented Generation using Azure AI Search
5. **Production Observability** - Full distributed tracing with OpenTelemetry
6. **State Management** - Persistent workflow state with Cosmos DB checkpointing
7. **LLM Evaluation** - Quality assessment using DeepEval metrics

### Objectives

- ✅ Provide a working multi-agent system template
- ✅ Demonstrate agent collaboration patterns (Planner → Researcher → Writer → Reviewer)
- ✅ Show best practices for Azure AI service integration
- ✅ Enable both local development and cloud deployment
- ✅ Support independent agent scaling and fault isolation
- ✅ Include comprehensive observability and logging

### Use Case: Social Media Content Generation

The default implementation generates LinkedIn posts through coordinated agent collaboration:

```
User Request → Planner → Researcher → Writer → Reviewer → Final Post
```

This pattern can be adapted for other multi-agent scenarios (code generation, document summarization, data analysis, etc.).

---

## 3. Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.11+ | Runtime environment |
| Docker Desktop | Latest | Local container orchestration |
| Azure CLI | 2.50+ | Azure resource management |
| Azure Developer CLI (azd) | Latest | Infrastructure deployment |
| Git | Latest | Source control |

### Required Azure Services

| Service | Purpose |
|---------|---------|
| Azure OpenAI | LLM inference (GPT-4o recommended) |
| Azure AI Search | Vector search for RAG |
| Azure Cosmos DB | Workflow state persistence |
| Azure Document Intelligence | PDF parsing (for data pipeline) |
| Azure Container Apps | Production deployment |
| Azure Container Registry | Container image storage |
| Azure Application Insights | Observability and monitoring |

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# =============================================================================
# Azure OpenAI Configuration
# =============================================================================
AZURE_OPENAI_ENDPOINT=https://your-openai-service.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# =============================================================================
# Azure OpenAI Embeddings (for Data Pipeline)
# =============================================================================
AZURE_OPENAI_EMBEDDINGS_ENDPOINT=https://your-openai-service.openai.azure.com/
AZURE_OPENAI_EMBEDDINGS_API_KEY=your-openai-api-key
AZURE_OPENAI_EMBEDDINGS_API_VERSION=2023-05-15
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-small

# =============================================================================
# Azure AI Search Configuration
# =============================================================================
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_ADMIN_KEY=your-search-admin-key
AZURE_SEARCH_INDEX_NAME=documents-index

# =============================================================================
# Azure Cosmos DB Configuration
# =============================================================================
AZURE_COSMOSDB_ENDPOINT=https://your-cosmosdb-account.documents.azure.com:443/
AZURE_COSMOSDB_KEY=your-cosmosdb-key
AZURE_COSMOSDB_DATABASE_NAME=multi-agent-db
AZURE_COSMOSDB_CONTAINER_NAME=checkpoints

# =============================================================================
# Azure Document Intelligence (for Data Pipeline)
# =============================================================================
AZURE_DI_ENDPOINT=https://your-di-service.cognitiveservices.azure.com/
AZURE_DI_KEY=your-di-key

# =============================================================================
# Azure Application Insights
# =============================================================================
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...

# =============================================================================
# Application Configuration
# =============================================================================
ENVIRONMENT=development
LOG_LEVEL=INFO

# =============================================================================
# Data Pipeline Configuration (Optional)
# =============================================================================
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
EMBEDDING_BATCH_SIZE=50
EMBEDDING_BATCH_DELAY=2.0
```

---

## 4. How to Run

### Quick Start (Local with Docker)

```powershell
# 1. Clone the repository
git clone <repository-url>
cd multi-agent-ai-system-lang-accelerator

# 2. Copy environment template and configure
Copy-Item .env.param .env
# Edit .env with your Azure credentials

# 3. Start all services
docker-compose up --build

# 4. Verify services are running
curl http://localhost:8000/health
```

### Available Endpoints

| Endpoint | Description |
|----------|-------------|
| http://localhost:8000/docs | API Documentation (Swagger UI) |
| http://localhost:8000/health | Orchestrator health check |
| http://localhost:8000/mcp/tools | List available MCP tools |
| http://localhost:8001/health | Planner Agent health |
| http://localhost:8002/health | Researcher Agent health |
| http://localhost:8003/health | Writer Agent health |
| http://localhost:8004/health | Reviewer Agent health |

### Using the MCP Client

```powershell
# Interactive mode
python clients/mcp_client.py
```

### API Usage Example

```python
import httpx

# Generate a LinkedIn post
response = httpx.post(
    "http://localhost:8000/mcp/tools/call",
    json={
        "method": "tools/call",
        "params": {
            "name": "generate_linkedin_post",
            "arguments": {
                "topic": "The future of AI in healthcare",
                "user_id": "user123"
            }
        }
    }
)
print(response.json())
```

---

## 5. Design

### System Architecture Diagram

<!-- TODO: Insert system architecture diagram here -->

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Client Applications                              │
│                    (Web UI, CLI, Copilot Studio, etc.)                        │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │ HTTP/MCP Protocol
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Orchestrator API (Port 8000)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐   │
│  │  FastMCP Server │  │  LangGraph      │  │  Cosmos DB Checkpointer     │   │
│  │  /mcp/*         │  │  Workflow       │  │  (State Persistence)         │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘   │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │ A2A Protocol (HTTP)
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Planner Agent  │  │ Researcher Agent│  │  Writer Agent   │  │ Reviewer Agent  │
│    (8001)       │  │    (8002)       │  │    (8003)       │  │    (8004)       │
│                 │  │                 │  │                 │  │                 │
│ Azure OpenAI    │  │ Azure AI Search │  │ Azure OpenAI    │  │ DeepEval        │
│ GPT-4o          │  │ Vector Search   │  │ GPT-4o          │  │ + Azure OpenAI  │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Workflow Orchestration

The system uses LangGraph to orchestrate a sequential workflow:

```
┌─────────┐    ┌────────────┐    ┌────────┐    ┌──────────┐    ┌─────────┐
│  START  │───▶│  PLANNER   │───▶│RESEARCH│───▶│  WRITER  │───▶│REVIEWER │
└─────────┘    └────────────┘    └────────┘    └──────────┘    └────┬────┘
                                                                     │
                                                                     ▼
                                                              ┌─────────────┐
                                                              │   Pass?     │
                                                              └──────┬──────┘
                                                                     │
                                              ┌──────────────────────┼──────────────────────┐
                                              │ NO (needs refinement)│ YES (approved)       │
                                              ▼                      ▼                      │
                                        ┌──────────┐           ┌──────────┐                 │
                                        │  WRITER  │──────────▶│   END    │◀────────────────┘
                                        │(refine)  │           └──────────┘
                                        └──────────┘
```

### Agent Roles and Responsibilities

| Agent | Port | Role | Responsibilities | Azure Services Used |
|-------|------|------|------------------|---------------------|
| **Orchestrator** | 8000 | Coordinator | Exposes MCP endpoints, manages workflow state, routes requests to agents | Cosmos DB (checkpointing), Application Insights |
| **Planner** | 8001 | Strategist | Analyzes topic, creates structured outline, identifies key points and research needs | Azure OpenAI (GPT-4o) |
| **Researcher** | 8002 | Information Gatherer | Searches knowledge base, retrieves relevant context using vector search | Azure AI Search (vector + semantic) |
| **Writer** | 8003 | Content Creator | Generates platform-specific content based on plan and research, handles refinements | Azure OpenAI (GPT-4o) |
| **Reviewer** | 8004 | Quality Assurer | Evaluates content using LLM metrics (relevancy, faithfulness), decides pass/refine | DeepEval, Azure OpenAI |

### A2A Protocol

All inter-agent communication uses a standardized A2A (Agent-to-Agent) protocol:

```python
# Request Format
{
    "agent_id": "planner",
    "thread_id": "unique-conversation-id",
    "user_id": "user123",
    "timestamp": "2025-01-28T10:30:00Z",
    "payload": {
        "topic": "AI in healthcare",
        "platform": "linkedin"
    },
    "metadata": {}
}

# Response Format
{
    "agent_id": "planner",
    "thread_id": "unique-conversation-id",
    "timestamp": "2025-01-28T10:30:05Z",
    "status": "success",  # success | error | partial
    "result": {
        "plan": "..."
    },
    "metadata": {}
}
```

### Key Design Principles

1. **Independent Scaling** - Each agent can scale independently (1-10 replicas)
2. **Fault Isolation** - Agent failures don't cascade to other services
3. **Technology Flexibility** - Agents can use different models/providers
4. **Observability** - Full distributed tracing via OpenTelemetry
5. **Idempotency** - State persistence enables workflow recovery

---

## 6. Data Pipeline

The data pipeline processes PDF documents and uploads them to Azure AI Search for RAG capabilities.

### Pipeline Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   PDF       │───▶│   Parse     │───▶│   Chunk     │───▶│   Embed     │
│   Files     │    │ (Doc Intel) │    │ (Text Split)│    │ (Ada-003)   │
└─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                                 │
                                                                 ▼
                                                         ┌─────────────┐
                                                         │   Upload    │
                                                         │ (AI Search) │
                                                         └─────────────┘
```

### Running the Pipeline

#### Step 1: Create the Search Index

```powershell
# Create index (skips if exists)
python datapipeline/create_search_index.py

# Force recreate index
python datapipeline/create_search_index.py --delete
```

#### Step 2: Add PDF Documents

```powershell
# Create data folder
New-Item -ItemType Directory -Path "datapipeline/data" -Force

# Add your PDFs
Copy-Item "C:\path\to\your\pdfs\*.pdf" "datapipeline/data\"
```

#### Step 3: Process and Upload

```powershell
# Process all PDFs in default location
python datapipeline/run_datapipeline.py

# Process from custom directory
python datapipeline/run_datapipeline.py "C:\path\to\your\pdfs"
```

### Pipeline Features

| Feature | Description |
|---------|-------------|
| **PDF Parsing** | Azure Document Intelligence extracts text with layout awareness |
| **Smart Chunking** | RecursiveCharacterTextSplitter with configurable size/overlap |
| **Batch Embeddings** | Rate-limited embedding generation with retry logic |
| **Idempotent Upload** | Merge-or-upload strategy prevents duplicates |
| **Vector + Semantic** | Hybrid search capabilities in the index |

### Pipeline Output Example

```
🚀 Starting PDF Data Pipeline
============================================================
Data directory: C:\code\project\datapipeline\data
PDFs found: 3
Target index: documents-index
============================================================

Processing: document1.pdf
📄 Parsing PDF: document1.pdf
   ✅ Parsed 10 pages
✂️  Chunking content from document1.pdf
   ✅ Created 45 chunks
🔢 Generating embeddings for 45 chunks
   ✅ All embeddings generated
☁️  Uploading 45 documents to Azure AI Search
   ✅ Upload complete: 45 succeeded, 0 failed

============================================================
Pipeline Complete!
============================================================
Total PDFs: 3
✅ Successful: 3
❌ Failed: 0
============================================================
```

---

## 7. Local vs Azure Deployment

### Local Development (Docker Compose)

**Best for:** Development, testing, debugging

```powershell
# Start all services
docker-compose up --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

| Aspect | Local |
|--------|-------|
| **Setup Time** | Minutes |
| **Cost** | Free (except Azure AI services) |
| **Scaling** | Single instance per service |
| **Networking** | Docker internal network |
| **Hot Reload** | Supported with volume mounts |

### Azure Container Apps Deployment

**Best for:** Production, staging, load testing

#### Step 1: Login and Initialize

```powershell
# Login to Azure
az login
azd auth login

# Initialize Azure Developer CLI
azd init
```

#### Step 2: Provision Infrastructure

```powershell
# Creates all Azure resources
azd provision
```

This creates:
- ✅ Container Apps Environment
- ✅ Container Registry
- ✅ 5 Container Apps (4 agents + orchestrator)
- ✅ Azure OpenAI, AI Search, Cosmos DB
- ✅ Application Insights & Log Analytics

#### Step 3: Build and Deploy

```powershell
# Automated deployment script
.\infra\deploy-all.ps1
```

Or manually:

```powershell
# Get registry name
$REGISTRY = az acr list --resource-group <rg> --query "[0].name" -o tsv

# Build each image
az acr build --registry $REGISTRY --image planner-agent:latest -f agents/planner_agent/Dockerfile .
az acr build --registry $REGISTRY --image researcher-agent:latest -f agents/researcher_agent/Dockerfile .
az acr build --registry $REGISTRY --image writer-agent:latest -f agents/writer_agent/Dockerfile .
az acr build --registry $REGISTRY --image reviewer-agent:latest -f agents/reviewer_agent/Dockerfile .
az acr build --registry $REGISTRY --image orchestrator-api:latest -f Dockerfile .
```

| Aspect | Azure Container Apps |
|--------|---------------------|
| **Setup Time** | ~15-20 minutes |
| **Cost** | Pay-per-use (consumption plan) |
| **Scaling** | Auto-scale 1-10 replicas per service |
| **Networking** | Internal VNET with managed certificates |
| **High Availability** | Multi-zone deployment |

### Service Port Mapping

| Service | Local Port | Azure (Internal) |
|---------|------------|------------------|
| Orchestrator | 8000 | External HTTPS |
| Planner | 8001 | Internal only |
| Researcher | 8002 | Internal only |
| Writer | 8003 | Internal only |
| Reviewer | 8004 | Internal only |

---

## 8. How to Undeploy/Delete

### Local Cleanup

```powershell
# Stop and remove containers
docker-compose down

# Remove images (optional)
docker-compose down --rmi all

# Remove volumes (optional - deletes data)
docker-compose down -v
```

### Azure Cleanup

#### Option 1: Using Azure Developer CLI (Recommended)

```powershell
# Delete all provisioned resources
azd down

# Confirm deletion when prompted
```

#### Option 2: Using Azure CLI

```powershell
# Get your resource group name
$RESOURCE_GROUP = "rg-your-environment-name"

# Delete the entire resource group
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

#### Option 3: Manual Deletion via Azure Portal

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to **Resource Groups**
3. Select the resource group created by `azd provision`
4. Click **Delete resource group**
5. Type the resource group name to confirm
6. Click **Delete**

### Cleanup Checklist

Ensure these resources are deleted:

- [ ] Container Apps (5 total)
- [ ] Container Apps Environment
- [ ] Container Registry
- [ ] Azure OpenAI resource
- [ ] Azure AI Search service
- [ ] Azure Cosmos DB account
- [ ] Application Insights
- [ ] Log Analytics Workspace
- [ ] Managed Identities
- [ ] Key Vault (if created)

---

## 9. Limitations

### Current Limitations

| Limitation | Description | Workaround |
|------------|-------------|------------|
| **Single Workflow** | Only LinkedIn post generation implemented | Extend `workflows/` for other use cases |
| **API Key Auth** | Uses API keys, not managed identity for local dev | Use managed identity in production |
| **English Only** | Prompts and evaluation optimized for English | Modify prompts for other languages |
| **Sequential Workflow** | Agents execute in strict sequence | Extend LangGraph for parallel execution |
| **Single Region** | Deployment to one Azure region | Use Azure Front Door for multi-region |
| **No UI** | CLI/API only, no web interface | Build custom UI using the API |
| **Max 3 Refinements** | Reviewer allows max 3 write-refine cycles | Configurable in workflow code |

### Known Issues

1. **Cold Start Latency** - Container Apps may have ~2-5s cold start delay
2. **Rate Limits** - Azure OpenAI rate limits apply; implement proper retry logic
3. **Large PDFs** - Documents >100 pages may timeout during processing

### Scalability Considerations

- **Orchestrator**: Can become bottleneck; consider horizontal scaling
- **AI Search**: Query performance depends on index size and SKU
- **Cosmos DB**: Choose appropriate partition key for high throughput

---

## 10. Summary

This Multi-Agent AI System LangGraph Accelerator provides a production-ready foundation for building scalable multi-agent applications on Azure. 

### What's Included

✅ **Complete Multi-Agent System** - 4 specialized agents + orchestrator  
✅ **Standards-Compliant MCP Server** - FastMCP with streaming support  
✅ **RAG Pipeline** - Document ingestion with vector search  
✅ **Production Observability** - OpenTelemetry + Azure Monitor  
✅ **Local & Cloud Deployment** - Docker Compose + Azure Container Apps  
✅ **LLM Evaluation** - DeepEval metrics for quality assurance  
✅ **Infrastructure as Code** - Bicep templates for Azure resources  

### Getting Started Checklist

1. [ ] Clone repository
2. [ ] Create Azure resources (OpenAI, AI Search, Cosmos DB)
3. [ ] Configure `.env` file with credentials
4. [ ] Run `docker-compose up --build`
5. [ ] Test API at http://localhost:8000/docs
6. [ ] (Optional) Run data pipeline for RAG capabilities
7. [ ] (Optional) Deploy to Azure with `azd provision`

### Additional Resources

- [FastMCP Integration Guide](docs/FASTMCP_INTEGRATION.md)
- [A2A Architecture Details](docs/A2A_ARCHITECTURE.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [MCP Client Documentation](clients/README.md)

### Contributing

Contributions are welcome! Please ensure:
- Code follows existing patterns
- Tests are included for new features
- Documentation is updated

### License

See [LICENSE](LICENSE) file for details.

---

**Built with ❤️ using LangGraph, FastMCP, and Azure AI Services**

