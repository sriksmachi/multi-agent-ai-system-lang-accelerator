param name string
param location string = resourceGroup().location
param tags object = {}

param containerAppsEnvironmentName string
param containerRegistryName string
param applicationInsightsName string
param storageAccountName string
param searchServiceName string

// Azure OpenAI parameters
param openAIEndpoint string = ''
@secure()
param openAIKey string = ''
param openAIDeploymentName string = ''
param openAIApiVersion string = '2024-12-01-preview'

// Agent service URLs
param plannerServiceUrl string = ''
param researcherServiceUrl string = ''
param writerServiceUrl string = ''
param reviewerServiceUrl string = ''
param supervisorServiceUrl string = ''

// Cosmos DB parameters
param cosmosEndpoint string = ''
@secure()
param cosmosPrimaryKey string = ''
param cosmosDatabaseName string = ''
param cosmosContainerName string = ''

param imageName string = ''

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppsEnvironmentName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource searchService 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchServiceName
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'orchestrator-api' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'appinsights-connection-string'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'storage-connection-string'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'search-admin-key'
          value: searchService.listAdminKeys().primaryKey
        }
        {
          name: 'cosmos-primary-key'
          value: cosmosPrimaryKey
        }
        {
          name: 'openai-api-key'
          value: openAIKey
        }
      ]
    }
    template: {
      containers: [
        {
          image: !empty(imageName) ? imageName : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'orchestrator-api'
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'AZURE_STORAGE_CONNECTION_STRING'
              secretRef: 'storage-connection-string'
            }
            {
              name: 'AZURE_SEARCH_ADMIN_KEY'
              secretRef: 'search-admin-key'
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: 'https://${searchService.name}.search.windows.net'
            }
            {
              name: 'AZURE_STORAGE_ACCOUNT_NAME'
              value: storageAccount.name
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: openAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              secretRef: 'openai-api-key'
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
              value: openAIDeploymentName
            }
            {
              name: 'AZURE_OPENAI_API_VERSION'
              value: openAIApiVersion
            }
            {
              name: 'PLANNER_SERVICE_URL'
              value: plannerServiceUrl
            }
            {
              name: 'RESEARCHER_SERVICE_URL'
              value: researcherServiceUrl
            }
            {
              name: 'WRITER_SERVICE_URL'
              value: writerServiceUrl
            }
            {
              name: 'REVIEWER_SERVICE_URL'
              value: reviewerServiceUrl
            }
            {
              name: 'SUPERVISOR_SERVICE_URL'
              value: supervisorServiceUrl
            }
            {
              name: 'AZURE_COSMOSDB_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'AZURE_COSMOSDB_KEY'
              secretRef: 'cosmos-primary-key'
            }
            {
              name: 'AZURE_COSMOSDB_DATABASE_NAME'
              value: cosmosDatabaseName
            }
            {
              name: 'AZURE_COSMOSDB_CONTAINER_NAME'
              value: cosmosContainerName
            }
            {
              name: 'ENVIRONMENT'
              value: 'production'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

// Grant Container App identity access to ACR
var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: containerRegistry
  name: guid(containerRegistry.id, app.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleDefinitionId)
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
output name string = app.name
output id string = app.id
