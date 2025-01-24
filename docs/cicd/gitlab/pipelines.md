---
tool: gitlab
category: cicd
version: "16.0"
topics:
  - pipelines
  - ci
  - cd
  - security
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md#gitops
    description: "GitOps with GitLab and Kubernetes"
  - path: /monitoring/prometheus/configuration.md#gitlab-metrics
    description: "Monitoring GitLab pipelines"
  - path: /security/scanning/container.md#gitlab
    description: "Container security scanning in GitLab"
  - path: /iac/terraform/gitlab_provider.md
    description: "Managing GitLab with Terraform"
---

# GitLab CI/CD Pipeline Patterns

## Complex Multi-Tool Workflows

### Complete DevSecOps Pipeline
```yaml
# .gitlab-ci.yml
include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Container-Scanning.gitlab-ci.yml
  - template: Security/DAST.gitlab-ci.yml

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: ""
  KUBERNETES_MEMORY_REQUEST: 1Gi
  KUBERNETES_MEMORY_LIMIT: 2Gi

stages:
  - test
  - scan
  - build
  - deploy
  - monitor
  - cleanup

.test:
  image: python:3.11-slim
  before_script:
    - pip install poetry
    - poetry install
  script:
    - poetry run pytest tests/
    - poetry run coverage report
  coverage: '/TOTAL.+ ([0-9]{1,3}%)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
      junit: test-results.xml

sast:
  stage: scan
  script:
    - semgrep ci
  variables:
    SCAN_KUBERNETES_MANIFESTS: "true"
  artifacts:
    reports:
      sast: gl-sast-report.json

container_scanning:
  stage: scan
  image: docker:stable
  services:
    - docker:dind
  script:
    - trivy image $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  artifacts:
    reports:
      container_scanning: gl-container-scanning-report.json

build:
  stage: build
  image: docker:stable
  services:
    - docker:dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  only:
    - main
    - tags

.deploy:
  image: 
    name: bitnami/kubectl:latest
    entrypoint: ['']
  script:
    - |
      kubectl create secret docker-registry gitlab-registry \
        --docker-server=$CI_REGISTRY \
        --docker-username=$CI_REGISTRY_USER \
        --docker-password=$CI_REGISTRY_PASSWORD \
        --docker-email=$GITLAB_USER_EMAIL \
        -n $KUBE_NAMESPACE \
        --dry-run=client -o yaml | kubectl apply -f -
    - |
      cat <<EOF > kustomization.yaml
      apiVersion: kustomize.config.k8s.io/v1beta1
      kind: Kustomization
      resources:
        - k8s/base
      namespace: $KUBE_NAMESPACE
      images:
        - name: $CI_REGISTRY_IMAGE
          newTag: $CI_COMMIT_SHA
      EOF
    - kubectl apply -k .

deploy_staging:
  extends: .deploy
  stage: deploy
  environment:
    name: staging
  variables:
    KUBE_NAMESPACE: staging
  only:
    - main

deploy_production:
  extends: .deploy
  stage: deploy
  environment:
    name: production
  variables:
    KUBE_NAMESPACE: production
  when: manual
  only:
    - tags

monitor:
  stage: monitor
  image: curlimages/curl
  script:
    - |
      curl -X POST $PROMETHEUS_WEBHOOK \
        -H 'Content-Type: application/json' \
        -d "{\"status\": \"success\", \"labels\": {\"pipeline\": \"$CI_PIPELINE_ID\"}}"
  only:
    - main
    - tags

cleanup:
  stage: cleanup
  image: docker:stable
  services:
    - docker:dind
  script:
    - |
      if [[ "$CI_COMMIT_REF_NAME" != "main" ]]; then
        docker rmi $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
      fi
  when: always
```

### GitOps with ArgoCD
```yaml
# .gitlab/agents/production/config.yaml
gitops:
  manifest_projects:
    - id: mygroup/gitops-manifests
      paths:
        - glob: '/manifests/production/**/*.{yaml,yml}'
      default_namespace: production
      reconcile_timeout: 3600s
      dry_run_strategy: none
      prune: true
      prune_timeout: 3600s
      prune_propagation_policy: foreground
      inventory_policy: must_match

# manifests/production/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: 'https://gitlab.com/mygroup/gitops-manifests.git'
    path: manifests/production
    targetRevision: HEAD
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

## Integration Patterns

### Multi-Cloud Deployment
```yaml
# .gitlab-ci.yml
.deploy_aws:
  extends: .deploy
  before_script:
    - aws eks get-token --cluster-name $AWS_CLUSTER_NAME | kubectl apply -f -

.deploy_azure:
  extends: .deploy
  before_script:
    - az aks get-credentials --resource-group $AZ_RESOURCE_GROUP --name $AZ_CLUSTER_NAME

deploy_aws_staging:
  extends: .deploy_aws
  stage: deploy
  environment:
    name: aws-staging
  variables:
    KUBE_NAMESPACE: staging
    AWS_CLUSTER_NAME: staging-cluster
  only:
    - main

deploy_azure_staging:
  extends: .deploy_azure
  stage: deploy
  environment:
    name: azure-staging
  variables:
    KUBE_NAMESPACE: staging
    AZ_RESOURCE_GROUP: staging-rg
    AZ_CLUSTER_NAME: staging-cluster
  only:
    - main
```

### Feature Flags and Canary Deployments
```yaml
# .gitlab-ci.yml
deploy_canary:
  extends: .deploy
  stage: deploy
  script:
    - |
      cat <<EOF > canary.yaml
      apiVersion: networking.istio.io/v1alpha3
      kind: VirtualService
      metadata:
        name: myapp
      spec:
        hosts:
        - myapp.example.com
        http:
        - route:
          - destination:
              host: myapp-canary
              subset: v2
            weight: 10
          - destination:
              host: myapp-stable
              subset: v1
            weight: 90
      EOF
    - kubectl apply -f canary.yaml
  environment:
    name: production
    url: https://myapp.example.com
  when: manual
```

## Common Issues and Solutions

### Error: Pipeline Timeout
```error
Pipeline failed: Job exceeded maximum execution time limit
```

Solution:
1. Optimize job configuration:
```yaml
job_name:
  timeout: 2h
  interruptible: true
  retry:
    max: 2
    when:
      - runner_system_failure
      - stuck_or_timeout_failure
```

2. Use caching:
```yaml
cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - .pip-cache/
    - vendor/
  policy: pull-push
```

### Error: Runner Out of Memory
```error
Job failed: OOM killed
```

Solution:
1. Adjust resource limits:
```yaml
job_name:
  script: npm run build
  variables:
    NODE_OPTIONS: --max_old_space_size=4096
  tags:
    - high-memory
```

2. Use resource classes:
```yaml
.high-memory:
  variables:
    KUBERNETES_MEMORY_REQUEST: 4Gi
    KUBERNETES_MEMORY_LIMIT: 8Gi
    KUBERNETES_CPU_REQUEST: 2
    KUBERNETES_CPU_LIMIT: 4

job_name:
  extends: .high-memory
  script:
    - ./memory-intensive-task
```
