---
tool: azure
category: cloud
version: "2023-01"
topics:
  - patterns
  - integrations
  - architecture
  - security
related_topics:
  - path: /iac/terraform/azure_provider.md#resources
    description: "Managing Azure resources with Terraform"
  - path: /containers/kubernetes/advanced_patterns.md#aks
    description: "AKS deployment patterns"
  - path: /monitoring/prometheus/configuration.md#azure-monitoring
    description: "Monitoring Azure resources"
  - path: /cicd/github_actions/workflows.md#azure-deployment
    description: "Deploying to Azure with GitHub Actions"
  - path: /iac/pulumi/configuration.md#azure
    description: "Azure infrastructure with Pulumi"
---

# Azure Cloud Patterns and Best Practices

## Complex Multi-Tool Workflows

### Complete Microservices Architecture
```yaml
# infrastructure/main.bicep
param location string = resourceGroup().location
param environmentName string
param aksClusterName string

// Virtual Network
resource vnet 'Microsoft.Network/virtualNetworks@2021-05-01' = {
  name: 'vnet-${environmentName}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.0.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'aks-subnet'
        properties: {
          addressPrefix: '10.0.0.0/20'
        }
      }
      {
        name: 'app-subnet'
        properties: {
          addressPrefix: '10.0.16.0/20'
          delegations: [
            {
              name: 'delegation'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
    ]
  }
}

// AKS Cluster
resource aksCluster 'Microsoft.ContainerService/managedClusters@2021-10-01' = {
  name: aksClusterName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: aksClusterName
    enableRBAC: true
    networkProfile: {
      networkPlugin: 'azure'
      networkPolicy: 'calico'
      serviceCidr: '172.16.0.0/16'
      dnsServiceIP: '172.16.0.10'
      dockerBridgeCidr: '172.17.0.1/16'
    }
    agentPoolProfiles: [
      {
        name: 'systempool'
        count: 3
        vmSize: 'Standard_DS2_v2'
        mode: 'System'
        maxPods: 30
        vnetSubnetID: vnet.properties.subnets[0].id
      }
    ]
  }
}

// Application Gateway
resource appGateway 'Microsoft.Network/applicationGateways@2021-05-01' = {
  name: 'appgw-${environmentName}'
  location: location
  properties: {
    sku: {
      name: 'WAF_v2'
      tier: 'WAF_v2'
    }
    gatewayIPConfigurations: [
      {
        name: 'appGatewayIpConfig'
        properties: {
          subnet: {
            id: vnet.properties.subnets[1].id
          }
        }
      }
    ]
    // ... other Application Gateway configurations
  }
}
```

### Security and Compliance Setup
```yaml
# security/policy.json
{
  "properties": {
    "displayName": "Secure Infrastructure Policy",
    "policyType": "Custom",
    "mode": "All",
    "parameters": {},
    "policyRule": {
      "if": {
        "allOf": [
          {
            "field": "type",
            "equals": "Microsoft.Storage/storageAccounts"
          },
          {
            "field": "Microsoft.Storage/storageAccounts/networkAcls.defaultAction",
            "notEquals": "Deny"
          }
        ]
      },
      "then": {
        "effect": "deny"
      }
    }
  }
}

# security/key-vault.bicep
resource keyVault 'Microsoft.KeyVault/vaults@2021-06-01-preview' = {
  name: 'kv-${environmentName}'
  location: location
  properties: {
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      ipRules: []
      virtualNetworkRules: [
        {
          id: vnet.properties.subnets[0].id
        }
      ]
    }
    sku: {
      family: 'A'
      name: 'standard'
    }
  }
}
```

## Integration Patterns

### Event-Driven Architecture
```yaml
# events/event-grid.bicep
resource eventGrid 'Microsoft.EventGrid/systemTopics@2021-12-01' = {
  name: 'evgt-${environmentName}'
  location: location
  properties: {
    source: storageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2021-12-01' = {
  parent: eventGrid
  name: 'storage-events'
  properties: {
    destination: {
      endpointType: 'ServiceBusQueue'
      properties: {
        resourceId: serviceBusQueue.id
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated',
        'Microsoft.Storage.BlobDeleted'
      ]
    }
  }
}

# events/service-bus.bicep
resource serviceBus 'Microsoft.ServiceBus/namespaces@2021-06-01-preview' = {
  name: 'sb-${environmentName}'
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {}
}

resource serviceBusQueue 'Microsoft.ServiceBus/namespaces/queues@2021-06-01-preview' = {
  parent: serviceBus
  name: 'storage-events'
  properties: {
    lockDuration: 'PT5M'
    maxSizeInMegabytes: 1024
    requiresDuplicateDetection: true
    requiresSession: false
  }
}
```

### Zero-Trust Network Architecture
```yaml
# network/security.bicep
resource networkSecurityGroup 'Microsoft.Network/networkSecurityGroups@2021-05-01' = {
  name: 'nsg-${environmentName}'
  location: location
  properties: {
    securityRules: [
      {
        name: 'deny-all-inbound'
        properties: {
          priority: 4096
          access: 'Deny'
          direction: 'Inbound'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
      {
        name: 'allow-azure-lb'
        properties: {
          priority: 100
          access: 'Allow'
          direction: 'Inbound'
          protocol: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2021-05-01' = {
  name: 'pe-${environmentName}'
  location: location
  properties: {
    subnet: {
      id: vnet.properties.subnets[1].id
    }
    privateLinkServiceConnections: [
      {
        name: 'storage-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}
```

## Common Issues and Solutions

### Error: VNET Integration Failed
```error
Failed to integrate VNET: Subnet delegation failed
```

Solution:
1. Check subnet delegation:
```azurecli
az network vnet subnet update \
  --name app-subnet \
  --resource-group myRG \
  --vnet-name myVNet \
  --delegations Microsoft.Web/serverFarms
```

2. Verify service endpoints:
```azurecli
az network vnet subnet update \
  --name app-subnet \
  --resource-group myRG \
  --vnet-name myVNet \
  --service-endpoints Microsoft.Web
```

### Error: AKS Node Communication
```error
Nodes in AKS cluster cannot communicate with each other
```

Solution:
1. Check network policy:
```azurecli
az aks update \
  --resource-group myRG \
  --name myAKS \
  --network-policy calico
```

2. Verify NSG rules:
```azurecli
az network nsg rule create \
  --resource-group myRG \
  --nsg-name myNSG \
  --name allow-aks \
  --priority 100 \
  --source-address-prefixes 10.0.0.0/20 \
  --destination-port-ranges "*" \
  --direction Inbound
```

### Error: Key Vault Access
```error
Access denied to Key Vault: Principal not authorized
```

Solution:
1. Enable managed identity:
```azurecli
az webapp identity assign \
  --resource-group myRG \
  --name myApp
```

2. Grant Key Vault access:
```azurecli
az keyvault set-policy \
  --name myKeyVault \
  --object-id <managed-identity-object-id> \
  --secret-permissions get list
```
