param parPrefix string
param parLocation string
@secure()
param parAzureApiKey string = ''

@secure()
param parOpenAiApiKey string = ''


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


// deploy key vault
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: '${parPrefix}-kv'
  location: parLocation
  properties: {    
    sku: {
      name: 'standard'
      family: 'A'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
  }

  // add secrets
  resource azureApiKey 'secrets' = if(parAzureApiKey != '') {
    name: 'azure-api-key'
    properties: {
      value: parAzureApiKey
    }
  }

  resource openaiApiKey 'secrets' = if(parOpenAiApiKey != '') {
    name: 'openai-api-key'
    properties: {
      value: parOpenAiApiKey
    }
  }

}


// create user assigned identity
resource acaId 'Microsoft.ManagedIdentity/userAssignedIdentities@2022-01-31-preview' = {
  name: '${parPrefix}-id'
  location: parLocation
}

// assign secrets reader role to identity
// see https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide?tabs=azure-cli
resource kvReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: acaId.properties.principalId
    principalType: 'ServicePrincipal'
  }
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
          image: '${acr.properties.loginServer}/openaiui:latest'
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

    }
    template: {
      containers: [
        {
          image: '${acr.properties.loginServer}/openaiapi:latest'
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                port: 5001
                path: '/probe'
              }
              initialDelaySeconds: 30
              periodSeconds: 15
            }
            {
              type: 'Readiness'
              httpGet: {
                port: 5001
                path: '/probe'
              }
            }
          ]
          name: 'api'
          env: [
            {
              name: 'TYPE'
              value: 'Azure'
            }
            {
              name: 'AZURE_KEY_VAULT_URL'
              value: keyVault.properties.vaultUri
            }
            {
              name: 'MANAGED_IDENTITY_CLIENT_ID'
              value: acaId.properties.clientId
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

