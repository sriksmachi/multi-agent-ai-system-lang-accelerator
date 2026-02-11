// Supervisor Agent Container App Module
// Orchestrates A2A agent communication and workflow management
param name string
param location string = resourceGroup().location
param tags object = {}
param containerAppsEnvironmentName string
param containerRegistryName string
param applicationInsightsName string
param openAIEndpoint string
@secure()
param openAIKey string
param openAIDeploymentName string
param openAIApiVersion string = '2024-12-01-preview'
param imageName string = ''

// Agent URLs for A2A discovery
param plannerServiceUrl string = ''
param researcherServiceUrl string = ''
param writerServiceUrl string = ''
param reviewerServiceUrl string = ''

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: containerAppsEnvironmentName
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource supervisorAgent 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'supervisor-agent' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true  // External for A2A orchestration access
        targetPort: 8005
        transport: 'http'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'OPTIONS']
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
          name: 'openai-api-key'
          value: openAIKey
        }
      ]
    }
    template: {
      containers: [
        {
          image: !empty(imageName) ? imageName : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          name: 'supervisor-agent'
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
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
              name: 'AGENT_NAME'
              value: 'supervisor'
            }
            {
              name: 'AGENT_PORT'
              value: '8005'
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
                port: 8005
              }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8005
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
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Role assignment for pulling from ACR
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(supervisorAgent.id, containerRegistry.id, 'AcrPull')
  scope: containerRegistry
  properties: {
    principalId: supervisorAgent.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull role
    principalType: 'ServicePrincipal'
  }
}

output fqdn string = supervisorAgent.properties.configuration.ingress.fqdn
output name string = supervisorAgent.name
output uri string = 'https://${supervisorAgent.properties.configuration.ingress.fqdn}'
output id string = supervisorAgent.id
