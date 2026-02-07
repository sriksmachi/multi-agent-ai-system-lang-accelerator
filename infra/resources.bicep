param environmentName string
param location string = resourceGroup().location
param principalId string
param tags object = {}

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'st${take(replace(environmentName, '-', ''), 9)}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Blob Services
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${environmentName}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${environmentName}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Azure AI Search
// NOTE: Using 'free' SKU for dev/test. Change to 'basic' or 'standard' for production.
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: 'srch-${environmentName}'
  location: location
  tags: tags
  sku: {
    name: 'free'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
  }
}

// Azure OpenAI
resource openAI 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: 'oai-${environmentName}'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: 'oai-${environmentName}${uniqueString(resourceGroup().id)}'
    publicNetworkAccess: 'Enabled'
  }
}

// Azure OpenAI GPT-4o Deployment
resource gpt4Deployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openAI
  name: 'gpt-5.2-chat'
  sku: {
    name: 'Standard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
  }
}

// Azure OpenAI Embeddings Deployment
resource embeddingsDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openAI
  name: 'text-embedding-3-small'
  dependsOn: [
    gpt4Deployment
  ]
  sku: {
    name: 'Standard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
  }
}

// Cosmos DB Account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: 'cosmos-${environmentName}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    publicNetworkAccess: 'Enabled'
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

// Cosmos DB Database
resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: 'content-generation-db'
  properties: {
    resource: {
      id: 'content-generation-db'
    }
  }
}

// Cosmos DB Container for Checkpoints
resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: 'chat-history'
  properties: {
    resource: {
      id: 'chat-history'
      partitionKey: {
        paths: [
          '/thread_id'
        ]
        kind: 'Hash'
      }
      defaultTtl: 5184000 // 60 days
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
  }
}

// Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'cr${replace(environmentName, '-', '')}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
    publicNetworkAccess: 'Enabled'
  }
}

// Container Apps Environment
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${environmentName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// AI Hub (AI Foundry)
resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: 'aih-${environmentName}'
  location: location
  tags: tags
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'AI Hub ${environmentName}'
    storageAccount: storageAccount.id
    keyVault: keyVault.id
    applicationInsights: appInsights.id
    publicNetworkAccess: 'Enabled'
  }
}

// Key Vault for AI Hub
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${replace(environmentName, '-', '')}${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

// AI Project (AI Foundry Project)
resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: 'aip-${environmentName}'
  location: location
  tags: tags
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'AI Project ${environmentName}'
    hubResourceId: aiHub.id
    publicNetworkAccess: 'Enabled'
  }
}

// Role Assignments for principal
var storageRoleDefinitionId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
var searchRoleDefinitionId = '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Contributor
var cosmosRoleDefinitionId = '00000000-0000-0000-0000-000000000002' // Cosmos DB Built-in Data Contributor
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  scope: storageAccount
  name: guid(storageAccount.id, principalId, storageRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageRoleDefinitionId)
    principalId: principalId
    principalType: 'User'
  }
}

resource searchRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  scope: searchService
  name: guid(searchService.id, principalId, searchRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchRoleDefinitionId)
    principalId: principalId
    principalType: 'User'
  }
}

resource openAIRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  scope: openAI
  name: guid(openAI.id, principalId, cognitiveServicesUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalId: principalId
    principalType: 'User'
  }
}

resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-11-15' = if (!empty(principalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, principalId, cosmosRoleDefinitionId)
  properties: {
    roleDefinitionId: '/${subscription().id}/resourceGroups/${resourceGroup().name}/providers/Microsoft.DocumentDB/databaseAccounts/${cosmosAccount.name}/sqlRoleDefinitions/${cosmosRoleDefinitionId}'
    principalId: principalId
    scope: cosmosAccount.id
  }
}

// Container App for Planner Agent
module plannerAgent './app/agent-planner.bicep' = {
  name: 'planner-agent'
  params: {
    name: 'ca-planner-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.name
    applicationInsightsName: appInsights.name
    openAIEndpoint: openAI.properties.endpoint
    openAIKey: openAI.listKeys().key1
    openAIDeploymentName: gpt4Deployment.name
    openAIApiVersion: '2024-12-01-preview'
  }
}

// Container App for Researcher Agent
module researcherAgent './app/agent-researcher.bicep' = {
  name: 'researcher-agent'
  params: {
    name: 'ca-researcher-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.name
    applicationInsightsName: appInsights.name
    searchServiceEndpoint: 'https://${searchService.name}.search.windows.net'
    searchServiceKey: searchService.listAdminKeys().primaryKey
    searchIndexName: 'documents-index'
  }
}

// Container App for Writer Agent
module writerAgent './app/agent-writer.bicep' = {
  name: 'writer-agent'
  params: {
    name: 'ca-writer-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.name
    applicationInsightsName: appInsights.name
    openAIEndpoint: openAI.properties.endpoint
    openAIKey: openAI.listKeys().key1
    openAIDeploymentName: gpt4Deployment.name
    openAIApiVersion: '2024-12-01-preview'
  }
}

// Container App for Reviewer Agent
module reviewerAgent './app/agent-reviewer.bicep' = {
  name: 'reviewer-agent'
  params: {
    name: 'ca-reviewer-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.name
    applicationInsightsName: appInsights.name
    openAIEndpoint: openAI.properties.endpoint
    openAIKey: openAI.listKeys().key1
    openAIDeploymentName: gpt4Deployment.name
    openAIApiVersion: '2024-12-01-preview'
  }
}

// Container App for Supervisor Agent (A2A Orchestrator)
module supervisorAgent './app/agent-supervisor.bicep' = {
  name: 'supervisor-agent'
  params: {
    name: 'ca-supervisor-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.name
    applicationInsightsName: appInsights.name
    openAIEndpoint: openAI.properties.endpoint
    openAIKey: openAI.listKeys().key1
    openAIDeploymentName: gpt4Deployment.name
    openAIApiVersion: '2024-12-01-preview'
    plannerServiceUrl: plannerAgent.outputs.uri
    researcherServiceUrl: researcherAgent.outputs.uri
    writerServiceUrl: writerAgent.outputs.uri
    reviewerServiceUrl: reviewerAgent.outputs.uri
  }
}

// Container App for Orchestrator API
module api './app/api.bicep' = {
  name: 'orchestrator-api'
  params: {
    name: 'ca-orchestrator-${environmentName}'
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironment.name
    containerRegistryName: containerRegistry.name
    applicationInsightsName: appInsights.name
    storageAccountName: storageAccount.name
    searchServiceName: searchService.name
    openAIEndpoint: openAI.properties.endpoint
    openAIKey: openAI.listKeys().key1
    openAIDeploymentName: gpt4Deployment.name
    openAIApiVersion: '2024-12-01-preview'
    plannerServiceUrl: plannerAgent.outputs.uri
    researcherServiceUrl: researcherAgent.outputs.uri
    writerServiceUrl: writerAgent.outputs.uri
    reviewerServiceUrl: reviewerAgent.outputs.uri
    supervisorServiceUrl: supervisorAgent.outputs.uri
    cosmosEndpoint: cosmosAccount.properties.documentEndpoint
    cosmosPrimaryKey: cosmosAccount.listKeys().primaryMasterKey
    cosmosDatabaseName: cosmosDatabase.name
    cosmosContainerName: cosmosContainer.name
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output applicationInsightsConnectionString string = appInsights.properties.ConnectionString
output applicationInsightsName string = appInsights.name
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchServiceName string = searchService.name
output searchServiceKey string = searchService.listAdminKeys().primaryKey
output aiFoundryName string = aiProject.name
output aiFoundryEndpoint string = aiProject.properties.discoveryUrl
output containerAppsEnvironmentName string = containerAppsEnvironment.name
output containerRegistryName string = containerRegistry.name
output containerRegistryEndpoint string = containerRegistry.properties.loginServer
output logAnalyticsWorkspaceName string = logAnalytics.name
output keyVaultName string = keyVault.name
output aiHubName string = aiHub.name
output openAIEndpoint string = openAI.properties.endpoint
output openAIName string = openAI.name
output openAIKey string = openAI.listKeys().key1
output openAIDeploymentName string = gpt4Deployment.name
output openAIEmbeddingsDeploymentName string = embeddingsDeployment.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosAccountName string = cosmosAccount.name
output cosmosPrimaryKey string = cosmosAccount.listKeys().primaryMasterKey
output cosmosDatabaseName string = cosmosDatabase.name
output cosmosContainerName string = cosmosContainer.name

// Agent Service Outputs
output plannerAgentUri string = plannerAgent.outputs.uri
output plannerAgentName string = plannerAgent.outputs.name
output plannerAgentFqdn string = plannerAgent.outputs.fqdn
output researcherAgentUri string = researcherAgent.outputs.uri
output researcherAgentName string = researcherAgent.outputs.name
output researcherAgentFqdn string = researcherAgent.outputs.fqdn
output writerAgentUri string = writerAgent.outputs.uri
output writerAgentName string = writerAgent.outputs.name
output writerAgentFqdn string = writerAgent.outputs.fqdn
output reviewerAgentUri string = reviewerAgent.outputs.uri
output reviewerAgentName string = reviewerAgent.outputs.name
output reviewerAgentFqdn string = reviewerAgent.outputs.fqdn
output supervisorAgentUri string = supervisorAgent.outputs.uri
output supervisorAgentName string = supervisorAgent.outputs.name
output supervisorAgentFqdn string = supervisorAgent.outputs.fqdn

// Orchestrator API Outputs
output orchestratorApiUri string = api.outputs.uri
output orchestratorApiName string = api.outputs.name
