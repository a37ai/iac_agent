---
tool: terraform
category: providers
version: "3.0"
topics:
  - azure
  - provider configuration
  - authentication
  - resources
---
# Azure Provider Configuration in Terraform

## Provider Setup

### Basic Configuration
```hcl
provider "azurerm" {
  features {}
  subscription_id = "your-subscription-id"
  tenant_id       = "your-tenant-id"
  client_id       = "your-client-id"
  client_secret   = "your-client-secret"
}
```

### Service Principal Authentication
```hcl
data "azuread_service_principal" "example" {
  display_name = "my-app"
}

resource "azurerm_role_assignment" "example" {
  scope                = azurerm_resource_group.example.id
  role_definition_name = "Contributor"
  principal_id         = data.azuread_service_principal.example.id
}
```

## Common Resources

### Virtual Network
```hcl
resource "azurerm_virtual_network" "example" {
  name                = "example-network"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name

  subnet {
    name           = "subnet1"
    address_prefix = "10.0.1.0/24"
  }

  tags = {
    environment = "Production"
  }
}
```

### AKS Cluster
```hcl
resource "azurerm_kubernetes_cluster" "example" {
  name                = "example-aks"
  location            = azurerm_resource_group.example.location
  resource_group_name = azurerm_resource_group.example.name
  dns_prefix          = "exampleaks"

  default_node_pool {
    name       = "default"
    node_count = 1
    vm_size    = "Standard_D2_v2"
  }

  identity {
    type = "SystemAssigned"
  }
}
```

## Common Issues and Solutions

### Error: Invalid Client Secret
```error
Error: Error acquiring token: Error acquiring token: parsing json result: parsing response from AAD: invalid_client: AADSTS7000215
```

Solution:
1. Check service principal:
```bash
az ad sp list --display-name "my-app"
```

2. Reset credentials:
```bash
az ad sp credential reset --name "my-app"
```

3. Update environment variables:
```bash
export ARM_CLIENT_ID="new-client-id"
export ARM_CLIENT_SECRET="new-client-secret"
```

### Error: Resource Provider Not Registered
```error
Error: Error registering provider 'Microsoft.Network'
```

Solution:
1. Register provider:
```bash
az provider register --namespace Microsoft.Network
```

2. Check registration status:
```bash
az provider show -n Microsoft.Network
```

3. Add provider registration to Terraform:
```hcl
resource "azurerm_resource_provider_registration" "example" {
  name = "Microsoft.Network"
}
```

### Error: Subnet Conflict
```error
Error: A resource with the ID "/subscriptions/.../subnets/subnet1" already exists
```

Solution:
1. Import existing subnet:
```bash
terraform import azurerm_subnet.example "/subscriptions/.../subnets/subnet1"
```

2. Use data source:
```hcl
data "azurerm_subnet" "example" {
  name                 = "subnet1"
  virtual_network_name = "example-network"
  resource_group_name  = "example-resources"
}
```

## Complex Workflows

### Multi-Region Deployment with Traffic Manager
```hcl
# Primary region resources
resource "azurerm_app_service" "primary" {
  name                = "app-primary"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.example.name
  app_service_plan_id = azurerm_app_service_plan.primary.id
}

# Secondary region resources
resource "azurerm_app_service" "secondary" {
  name                = "app-secondary"
  location            = "westus"
  resource_group_name = azurerm_resource_group.example.name
  app_service_plan_id = azurerm_app_service_plan.secondary.id
}

# Traffic Manager profile
resource "azurerm_traffic_manager_profile" "example" {
  name                = "example-profile"
  resource_group_name = azurerm_resource_group.example.name
  traffic_routing_method = "Priority"

  dns_config {
    relative_name = "example-profile"
    ttl          = 100
  }

  monitor_config {
    protocol = "HTTPS"
    port     = 443
    path     = "/"
  }
}

# Traffic Manager endpoints
resource "azurerm_traffic_manager_endpoint" "primary" {
  name                = "primary"
  resource_group_name = azurerm_resource_group.example.name
  profile_name        = azurerm_traffic_manager_profile.example.name
  target_resource_id  = azurerm_app_service.primary.id
  type                = "azureEndpoints"
  priority            = 1
}

resource "azurerm_traffic_manager_endpoint" "secondary" {
  name                = "secondary"
  resource_group_name = azurerm_resource_group.example.name
  profile_name        = azurerm_traffic_manager_profile.example.name
  target_resource_id  = azurerm_app_service.secondary.id
  type                = "azureEndpoints"
  priority            = 2
}
```
