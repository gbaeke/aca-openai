param parPrefix string
param parLocation string
@secure()
param parAzureApiKey string

// azure container registry
resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: '${parPrefix}acr${uniqueString(resourceGroup().id)}'
  location: parLocation
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: true
  }
}

// create user assigned identity
resource acaId 'Microsoft.ManagedIdentity/userAssignedIdentities@2022-01-31-preview' = {
  name: '${parPrefix}-id'
  location: parLocation
}

// assign acr pull role to identity
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, acaId.id, 'AcrPull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: acaId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// log analytics workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${parPrefix}-la'
  location: parLocation
  properties: {
    sku: {
      name: 'PerGB2018'
    }
  }
}

// app insights
resource appInsights 'Microsoft.Insights/components@2020-02-02-preview' = {
  name: '${parPrefix}-ai'
  location: parLocation
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: logAnalyticsWorkspace.id    
  }
}

// deploy container apps environment
resource acaEnv 'Microsoft.App/managedEnvironments@2022-03-01' = {
  name: '${parPrefix}-aca-env'
  location: parLocation
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: listKeys(logAnalyticsWorkspace.id, logAnalyticsWorkspace.apiVersion).primarySharedKey
      }
    }
    daprAIConnectionString: appInsights.properties.ConnectionString
    
  }
}


// deploy ui as a container app
resource webui 'Microsoft.App/containerApps@2022-06-01-preview' = {
  name: '${parPrefix}-webui'
  location: parLocation
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${acaId.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      dapr: {
        enabled: true
        appPort:5000
        appId: 'webui'
      }
      ingress: {
        external: true
        targetPort: 5000

      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: acaId.id
        }
      ]
    }
    template: {
      containers: [
        {
          image: 'gbaeke/openaiui:1.0.0'
          name: 'webui'
          env: [
            {
              name: 'INVOKE_URL'
              value: 'http://localhost:3500/v1.0/invoke/openai/method/generate'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }

    }

  }
}

// deploy api as a container app
resource api 'Microsoft.App/containerApps@2022-06-01-preview' = {
  name: '${parPrefix}-api'
  location: parLocation
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${acaId.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      dapr: {
        enabled: true
        appId: 'openai'
      }
      ingress: {
        external: false
        targetPort: 5001
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: acaId.id
        }
      ]
      secrets: [
        {
          name: 'apikey'
          value: parAzureApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          image: 'gbaeke/openaiapi:1.0.0'
          name: 'api'
          env: [
            {
              name: 'TYPE'
              value: 'Azure'
            }
            {
              name: 'AZURE_API_KEY'
              secretRef: 'apikey'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
      
    }

  }
}

