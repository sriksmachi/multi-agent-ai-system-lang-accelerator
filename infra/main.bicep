targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

// Tags that should be applied to all resources
var tags = {
  'azd-env-name': environmentName
}

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

// Core infrastructure module
module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    environmentName: environmentName
    location: location
    principalId: principalId
    tags: tags
  }
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name

// Storage Account outputs
output AZURE_STORAGE_ACCOUNT_NAME string = resources.outputs.storageAccountName
output AZURE_STORAGE_ACCOUNT_ID string = resources.outputs.storageAccountId

// Application Insights outputs
output APPLICATIONINSIGHTS_CONNECTION_STRING string = resources.outputs.applicationInsightsConnectionString
output APPLICATIONINSIGHTS_NAME string = resources.outputs.applicationInsightsName

// AI Search outputs
output AZURE_SEARCH_ENDPOINT string = resources.outputs.searchServiceEndpoint
output AZURE_SEARCH_NAME string = resources.outputs.searchServiceName
output AZURE_SEARCH_ADMIN_KEY string = resources.outputs.searchServiceKey
output AZURE_SEARCH_INDEX_NAME string = 'documents-index'

// Azure OpenAI outputs
output AZURE_OPENAI_ENDPOINT string = resources.outputs.openAIEndpoint
output AZURE_OPENAI_NAME string = resources.outputs.openAIName
output AZURE_OPENAI_API_KEY string = resources.outputs.openAIKey
output AZURE_OPENAI_DEPLOYMENT_NAME string = resources.outputs.openAIDeploymentName
output AZURE_OPENAI_API_VERSION string = '2024-12-01-preview'
output AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT string = resources.outputs.openAIEmbeddingsDeploymentName
output AZURE_OPENAI_EMBEDDINGS_ENDPOINT string = resources.outputs.openAIEndpoint
output AZURE_OPENAI_EMBEDDINGS_API_KEY string = resources.outputs.openAIKey
output AZURE_OPENAI_EMBEDDINGS_API_VERSION string = '2023-05-15'
output AZURE_DEPLOYMENT_NAME string = resources.outputs.openAIDeploymentName
output AZURE_MODEL_NAME string = resources.outputs.openAIDeploymentName

// Cosmos DB outputs
output COSMOS_ENDPOINT string = resources.outputs.cosmosEndpoint
output COSMOS_ACCOUNT_NAME string = resources.outputs.cosmosAccountName
output COSMOS_PRIMARY_KEY string = resources.outputs.cosmosPrimaryKey
output COSMOS_DATABASE_NAME string = resources.outputs.cosmosDatabaseName
output COSMOS_CHECKPOINTS_CONTAINER string = resources.outputs.cosmosContainerName

// AI Foundry outputs
output AZURE_AI_FOUNDRY_NAME string = resources.outputs.aiFoundryName
output AZURE_AI_FOUNDRY_ENDPOINT string = resources.outputs.aiFoundryEndpoint

// Container Apps outputs
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = resources.outputs.containerAppsEnvironmentName
output AZURE_CONTAINER_REGISTRY_NAME string = resources.outputs.containerRegistryName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryEndpoint

// Orchestrator API outputs
output API_URI string = resources.outputs.orchestratorApiUri
output API_NAME string = resources.outputs.orchestratorApiName

// Agent Service outputs
output PLANNER_AGENT_URI string = resources.outputs.plannerAgentUri
output PLANNER_AGENT_NAME string = resources.outputs.plannerAgentName
output RESEARCHER_AGENT_URI string = resources.outputs.researcherAgentUri
output RESEARCHER_AGENT_NAME string = resources.outputs.researcherAgentName
output WRITER_AGENT_URI string = resources.outputs.writerAgentUri
output WRITER_AGENT_NAME string = resources.outputs.writerAgentName
output REVIEWER_AGENT_URI string = resources.outputs.reviewerAgentUri
output REVIEWER_AGENT_NAME string = resources.outputs.reviewerAgentName
output SUPERVISOR_AGENT_URI string = resources.outputs.supervisorAgentUri
output SUPERVISOR_AGENT_NAME string = resources.outputs.supervisorAgentName

// Additional outputs
output AZURE_KEY_VAULT_NAME string = resources.outputs.keyVaultName
output AZURE_LOG_ANALYTICS_WORKSPACE_NAME string = resources.outputs.logAnalyticsWorkspaceName
output AZURE_AI_HUB_NAME string = resources.outputs.aiHubName
