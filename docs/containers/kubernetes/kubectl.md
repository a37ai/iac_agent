---
tool: kubernetes
category: cli
version: "1.28"
topics:
  - kubectl
  - cluster management
  - pod operations
---
# Kubectl Command Line Tool

## Common Commands

### Cluster Operations
```bash
# Get cluster info
kubectl cluster-info

# Get nodes
kubectl get nodes

# Get all resources in all namespaces
kubectl get all --all-namespaces
```

## Common Issues and Solutions

### Error: Unable to connect to the server
```error
The connection to the server localhost:8080 was refused
```

Solution:
1. Check kubeconfig:
```bash
echo $KUBECONFIG
cat ~/.kube/config
```

2. Verify cluster is running:
```bash
minikube status  # If using minikube
kind get clusters  # If using kind
```

3. Ensure proper context:
```bash
kubectl config get-contexts
kubectl config use-context my-context
```

### Error: Unauthorized
```error
Error from server (Forbidden): pods is forbidden
```

Solution:
1. Check RBAC permissions:
```bash
kubectl auth can-i get pods
kubectl auth can-i create deployments
```

2. Verify service account:
```bash
kubectl get serviceaccount
kubectl describe serviceaccount default
```

### Error: ImagePullBackOff
```error
Back-off pulling image "xyz"
```

Solution:
1. Check image name and tag
2. Verify registry credentials:
```bash
kubectl create secret docker-registry regcred \
  --docker-server=<registry-server> \
  --docker-username=<username> \
  --docker-password=<password>
```
3. Add imagePullSecrets to pod spec
