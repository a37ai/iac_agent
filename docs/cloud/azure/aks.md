---
tool: azure
category: containers
version: "2023-01-01"
topics:
  - aks
  - kubernetes
  - containers
---
# Azure Kubernetes Service (AKS)

## Common Operations

### Cluster Management
```bash
# Create AKS cluster
az aks create \
  --resource-group myResourceGroup \
  --name myAKSCluster \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials \
  --resource-group myResourceGroup \
  --name myAKSCluster
```

## Common Issues and Solutions

### Error: AADSTS700016
```error
AADSTS700016: Application with identifier 'xyz' was not found
```

Solution:
1. Check service principal:
```bash
az ad sp show --id <app-id>
```

2. Create new service principal:
```bash
az ad sp create-for-rbac --skip-assignment \
  --name myAKSClusterServicePrincipal
```

3. Assign roles:
```bash
az role assignment create \
  --assignee <app-id> \
  --scope <resource-id> \
  --role Contributor
```

### Error: Node Pool Issues
```error
Operation failed with status: 'Failed'. Details: Agent node 'xyz' not ready after 10m0s
```

Solution:
1. Check node status:
```bash
kubectl get nodes
kubectl describe node <node-name>
```

2. Scale node pool:
```bash
az aks nodepool scale \
  --resource-group myResourceGroup \
  --cluster-name myAKSCluster \
  --name mynodepool \
  --node-count 3
```

3. Update node pool:
```bash
az aks nodepool upgrade \
  --resource-group myResourceGroup \
  --cluster-name myAKSCluster \
  --name mynodepool \
  --kubernetes-version 1.25.5
```
