# Infrastructure

Bicep templates for Azure deployment. See [main README](../README.md#7-local-vs-azure-deployment) for deployment steps.

## Resources Created

| Resource | Description |
|----------|-------------|
| Azure OpenAI | GPT-4o chat + embeddings |
| Cosmos DB | Serverless checkpointing |
| AI Search | Vector search |
| Container Registry | Image repository |
| Container Apps Environment | Serverless hosting |
| Container Apps (6) | Agents + Orchestrator |
| Application Insights | Tracing |
| Key Vault | Secrets |

## Naming Convention

- Resource Group: `rg-{environmentName}`
- Azure OpenAI: `oai-{environmentName}`
- Cosmos DB: `cosmos-{environmentName}{uniqueString}`
- AI Search: `srch-{environmentName}`
- Container Registry: `cr{environmentName}{uniqueString}`
- Container Apps: `ca-{service}-{environmentName}`

## Cost Optimization

Default tiers:
- **Azure OpenAI**: Standard, 50 TPM
- **Cosmos DB**: Serverless (pay-per-request)
- **AI Search**: Basic
- **Container Registry**: Basic

## Manual Bicep Deployment

If not using `azd provision`, deploy directly with Azure CLI:

```bash
cd infra
az deployment sub create \
  --name multi-agent-deployment \
  --location eastus \
  --template-file main.bicep \
  --parameters main.parameters.json
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| OpenAI deployment fails | Try different regions: `eastus`, `swedencentral`, `francecentral` |
| Insufficient OpenAI quota | Request increase in Azure Portal > Azure OpenAI > Quotas |
| Role assignment fails | Ensure Owner or User Access Administrator role |
| Cannot connect to Cosmos DB | Enable "Allow access from Azure services" in firewall |
