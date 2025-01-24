---
tool: github_actions
category: cicd
version: "2.0"
topics:
  - workflows
  - pipelines
  - automation
  - deployment
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md#deployment
    description: "Kubernetes deployment strategies"
  - path: /iac/terraform/aws_provider.md#github-actions
    description: "AWS infrastructure automation"
  - path: /monitoring/prometheus/configuration.md#github-metrics
    description: "Monitoring GitHub Actions with Prometheus"
  - path: /containers/docker/basics.md#github-registry
    description: "Using GitHub Container Registry"
  - path: /cicd/gitlab/ci_cd.md#migration
    description: "Migrating from GitLab CI to GitHub Actions"
  - path: /iac/pulumi/configuration.md#github-actions
    description: "Automating Pulumi with GitHub Actions"
---

# GitHub Actions Workflows

## Common Configurations

### Basic Workflow
```yaml
name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Build
      run: |
        make build
```

## Common Issues and Solutions

### Error: Resource not accessible by integration
```error
Resource not accessible by integration
```

Solution:
1. Check repository permissions:
   - Go to Settings > Actions > General
   - Ensure "Allow all actions and reusable workflows" is enabled

2. For private repositories:
```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
```

### Error: Runner error
```error
Can't find 'node' in PATH
```

Solution:
1. Use setup actions:
```yaml
steps:
  - uses: actions/setup-node@v3
    with:
      node-version: '16'
```

### Error: Secrets not available
```error
Error: Secrets must be explicitly configured
```

Solution:
1. Add secrets in repository:
   - Go to Settings > Secrets and variables > Actions
   - Add New repository secret

2. Use secrets in workflow:
```yaml
steps:
  - name: Deploy
    env:
      API_TOKEN: ${{ secrets.API_TOKEN }}
    run: ./deploy.sh
```

## Complex Multi-Tool Workflows

### Complete CI/CD Pipeline with Infrastructure
```yaml
name: CI/CD with Infrastructure

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  AWS_REGION: us-west-2
  EKS_CLUSTER: production
  ECR_REPOSITORY: my-app

jobs:
  infrastructure:
    runs-on: ubuntu-latest
    outputs:
      ecr_registry: ${{ steps.login-ecr.outputs.registry }}
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v1
      with:
        role-to-assume: arn:aws:iam::123456789012:role/github-actions
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Setup Terraform
      uses: hashicorp/setup-terraform@v2
    
    - name: Terraform Init
      run: terraform init
    
    - name: Terraform Plan
      run: terraform plan -out=tfplan
      
    - name: Terraform Apply
      if: github.ref == 'refs/heads/main'
      run: terraform apply -auto-approve tfplan
    
    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1

  build:
    needs: infrastructure
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: ${{ needs.infrastructure.outputs.ecr_registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  security-scan:
    needs: build
    runs-on: ubuntu-latest
    steps:
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ needs.infrastructure.outputs.ecr_registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'
    
    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  deploy:
    needs: [build, security-scan]
    runs-on: ubuntu-latest
    environment: production
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up kubectl
      uses: azure/setup-kubectl@v3
    
    - name: Update kube config
      run: aws eks update-kubeconfig --name ${{ env.EKS_CLUSTER }} --region ${{ env.AWS_REGION }}
    
    - name: Deploy to EKS
      run: |
        # Update image tag in Kubernetes manifests
        sed -i "s|IMAGE_TAG|${{ github.sha }}|g" k8s/deployment.yaml
        
        # Apply manifests
        kubectl apply -f k8s/
        
        # Wait for rollout
        kubectl rollout status deployment/my-app -n default

  monitoring:
    needs: deploy
    runs-on: ubuntu-latest
    steps:
    - name: Configure Prometheus Alert
      run: |
        curl -X POST ${{ secrets.PROMETHEUS_API }}/api/v1/alerts \
          -H "Content-Type: application/json" \
          -d '{
            "alert": "DeploymentComplete",
            "expr": "kube_deployment_status_replicas_available{deployment=\"my-app\"} > 0",
            "for": "5m",
            "labels": {
              "severity": "info",
              "deployment": "github-actions"
            }
          }'
    
    - name: Update Grafana Dashboard
      run: |
        curl -X POST ${{ secrets.GRAFANA_API }}/api/dashboards/db \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer ${{ secrets.GRAFANA_TOKEN }}" \
          -d @monitoring/dashboard.json
```

### GitOps Workflow with FluxCD
```yaml
name: GitOps with FluxCD

on:
  push:
    branches: [ main ]
    paths:
      - 'k8s/**'
      - '.github/workflows/gitops.yml'

jobs:
  gitops:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Flux
      uses: fluxcd/flux2/action@main
    
    - name: Check Flux installation
      run: flux check --pre
    
    - name: Create k8s Secret
      run: |
        kubectl create secret generic repository-auth \
          --namespace=flux-system \
          --from-literal=username=${{ secrets.GIT_USER }} \
          --from-literal=password=${{ secrets.GIT_TOKEN }} \
          --dry-run=client -o yaml | kubectl apply -f -
    
    - name: Setup Git Repository
      run: |
        flux create source git my-app \
          --url=https://github.com/${{ github.repository }} \
          --branch=main \
          --interval=1m \
          --secret-ref=repository-auth
    
    - name: Setup Kustomization
      run: |
        flux create kustomization my-app \
          --source=my-app \
          --path="./k8s" \
          --prune=true \
          --interval=5m \
          --health-check="Deployment/my-app.default"
    
    - name: Verify Reconciliation
      run: |
        flux get kustomizations --watch
        flux get all
```

### Multi-Environment Deployment with Approval
```yaml
name: Multi-Environment Deploy

on:
  push:
    tags:
      - 'v*'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Validate Kubernetes manifests
      uses: instrumenta/kubeval-action@master
    
    - name: Lint Helm charts
      run: |
        helm lint charts/*
    
    - name: Run integration tests
      run: |
        go test ./... -tags=integration

  staging:
    needs: validate
    runs-on: ubuntu-latest
    environment: staging
    steps:
    - name: Deploy to staging
      uses: azure/k8s-deploy@v1
      with:
        manifests: |
          k8s/staging/
        images: |
          my-app:${{ github.sha }}
    
    - name: Run smoke tests
      run: |
        ./tests/smoke-test.sh https://staging.example.com

  production:
    needs: staging
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://example.com
    steps:
    - name: Create deployment
      uses: chrnorm/deployment-action@v2
      id: deployment
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
        environment: production
        ref: ${{ github.sha }}
    
    - name: Deploy to production
      uses: azure/k8s-deploy@v1
      with:
        manifests: |
          k8s/production/
        images: |
          my-app:${{ github.sha }}
    
    - name: Update deployment status
      if: always()
      uses: chrnorm/deployment-status@v2
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
        deployment-id: ${{ steps.deployment.outputs.deployment_id }}
        state: ${{ job.status }}
