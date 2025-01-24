---
tool: kubernetes
category: containers
version: "1.27"
topics:
  - patterns
  - operators
  - custom resources
  - networking
related_topics:
  - path: /iac/terraform/aws_provider.md#eks-cluster
    description: "Setting up EKS clusters with Terraform"
  - path: /iac/terraform/azure_provider.md#aks-cluster
    description: "Setting up AKS clusters with Terraform"
  - path: /iac/terraform/gcp_provider.md#gke-cluster
    description: "Setting up GKE clusters with Terraform"
  - path: /cicd/github_actions/workflows.md#kubernetes-deployment
    description: "Deploying to Kubernetes with GitHub Actions"
  - path: /monitoring/prometheus/configuration.md#kubernetes-monitoring
    description: "Monitoring Kubernetes clusters with Prometheus"
  - path: /monitoring/grafana/dashboards.md#kubernetes-dashboards
    description: "Kubernetes dashboards in Grafana"
---
# Kubernetes Advanced Patterns

## Custom Resource Definitions (CRDs)

### Basic CRD Definition
```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backups.stable.example.com
spec:
  group: stable.example.com
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                cronSpec:
                  type: string
                image:
                  type: string
  scope: Namespaced
  names:
    plural: backups
    singular: backup
    kind: Backup
    shortNames:
      - bk
```

### Custom Controller
```go
package main

import (
    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/rest"
)

func main() {
    config, err := rest.InClusterConfig()
    if err != nil {
        panic(err.Error())
    }
    
    clientset, err := kubernetes.NewForConfig(config)
    if err != nil {
        panic(err.Error())
    }

    // Watch for Backup resources
    watchlist := cache.NewListWatchFromClient(
        clientset.RESTClient(),
        "backups",
        corev1.NamespaceAll,
        fields.Everything(),
    )
}
```

## Advanced Networking

### Network Policies
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restrict-traffic
spec:
  podSelector:
    matchLabels:
      app: web
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              purpose: production
        - podSelector:
            matchLabels:
              role: frontend
      ports:
        - protocol: TCP
          port: 80
  egress:
    - to:
        - ipBlock:
            cidr: 10.0.0.0/24
      ports:
        - protocol: TCP
          port: 5432
```

### Service Mesh (Istio)
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: reviews-route
spec:
  hosts:
    - reviews
  http:
    - match:
        - headers:
            end-user:
              exact: jason
      route:
        - destination:
            host: reviews
            subset: v2
    - route:
        - destination:
            host: reviews
            subset: v3
```

## Advanced Storage

### Storage Class with Volume Expansion
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: standard-expandable
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp2
allowVolumeExpansion: true
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
```

### StatefulSet with Volume Claims
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: "nginx"
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.14.2
        ports:
        - containerPort: 80
          name: web
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html
  volumeClaimTemplates:
  - metadata:
      name: www
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "standard-expandable"
      resources:
        requests:
          storage: 1Gi
```

## Common Issues and Solutions

### Error: ImagePullBackOff
```error
Failed to pull image: rpc error: code = Unknown desc = Error response from daemon
```

Solution:
1. Check image name and tag:
```bash
kubectl describe pod <pod-name>
```

2. Add image pull secret:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: registry-secret
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-docker-config>
```

3. Update pod spec:
```yaml
spec:
  imagePullSecrets:
    - name: registry-secret
```

### Error: CrashLoopBackOff
```error
Back-off restarting failed container
```

Solution:
1. Check logs:
```bash
kubectl logs <pod-name> --previous
```

2. Add readiness probe:
```yaml
readinessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

3. Set resource limits:
```yaml
resources:
  limits:
    memory: "128Mi"
    cpu: "500m"
  requests:
    memory: "64Mi"
    cpu: "250m"
```

## Complex Workflows

### Blue-Green Deployment
```yaml
# Service pointing to blue deployment
apiVersion: v1
kind: Service
metadata:
  name: my-app
  labels:
    app: my-app
spec:
  selector:
    app: my-app
    version: blue
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080

---
# Blue deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
      version: blue
  template:
    metadata:
      labels:
        app: my-app
        version: blue
    spec:
      containers:
        - name: my-app
          image: my-app:1.0
          ports:
            - containerPort: 8080

---
# Green deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
      version: green
  template:
    metadata:
      labels:
        app: my-app
        version: green
    spec:
      containers:
        - name: my-app
          image: my-app:2.0
          ports:
            - containerPort: 8080
```

### Canary Deployment with Istio
```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: my-app-vsvc
spec:
  hosts:
    - my-app
  http:
    - route:
      - destination:
          host: my-app
          subset: v1
        weight: 90
      - destination:
          host: my-app
          subset: v2
        weight: 10

---
apiVersion: networking.istio.io/v1alpha3
kind: DestinationRule
metadata:
  name: my-app-destrule
spec:
  host: my-app
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
