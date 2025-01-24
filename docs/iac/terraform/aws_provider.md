---
tool: terraform
category: providers
version: "5.0"
topics:
  - aws
  - provider configuration
  - resources
  - infrastructure
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md#eks-deployment
    description: "Advanced EKS deployment patterns"
  - path: /cicd/github_actions/workflows.md#terraform-automation
    description: "Automating Terraform with GitHub Actions"
  - path: /monitoring/prometheus/configuration.md#aws-monitoring
    description: "Monitoring AWS resources with Prometheus"
  - path: /monitoring/grafana/dashboards.md#aws-dashboards
    description: "AWS dashboards in Grafana"
  - path: /iac/cloudformation/templates.md#migration
    description: "Migrating from CloudFormation to Terraform"
  - path: /containers/docker/basics.md#aws-ecr
    description: "Working with AWS ECR"
---

# AWS Provider Configuration in Terraform

## Common Configuration

### Basic Provider Configuration
```hcl
provider "aws" {
  region = "us-west-2"
  access_key = "my-access-key"
  secret_key = "my-secret-key"
}
```

## Common Issues and Solutions

### Error: AWS Provider Configuration Not Found
```error
Error: No valid credential sources found for AWS Provider
```

Solution:
1. Check AWS credentials:
```bash
aws configure list
aws sts get-caller-identity
```

2. Set environment variables:
```bash
export AWS_ACCESS_KEY_ID="anaccesskey"
export AWS_SECRET_ACCESS_KEY="asecretkey"
```

3. Use shared credentials file:
```hcl
provider "aws" {
  region                   = "us-west-2"
  shared_credentials_files = ["~/.aws/credentials"]
  profile                  = "custom-profile"
}
```

### Error: Invalid Region
```error
Error: Invalid region: xyz
```

Solution:
1. Use valid AWS region from: https://docs.aws.amazon.com/general/latest/gr/rande.html
2. Check region spelling
3. Ensure region is available for your account

### Error: Access Denied
```error
Error: AccessDenied: Access Denied
```

Solution:
1. Verify IAM permissions
2. Check IAM policy attachments
3. Ensure MFA is configured if required

## Complex Multi-Tool Workflows

### Complete EKS Setup with Monitoring
```hcl
# 1. EKS Cluster Setup
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "my-eks"
  cluster_version = "1.27"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      desired_size = 2
      min_size     = 1
      max_size     = 3

      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
    }
  }
}

# 2. Prometheus and Grafana Helm Releases
resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "prometheus"
  namespace  = "monitoring"

  set {
    name  = "server.persistentVolume.storageClass"
    value = aws_eks_addon.ebs_csi.storage_class
  }

  depends_on = [module.eks]
}

resource "helm_release" "grafana" {
  name       = "grafana"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "grafana"
  namespace  = "monitoring"

  set {
    name  = "persistence.storageClassName"
    value = aws_eks_addon.ebs_csi.storage_class
  }

  depends_on = [helm_release.prometheus]
}

# 3. ECR Repository for Application
resource "aws_ecr_repository" "app" {
  name                 = "my-app"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# 4. CI/CD IAM Roles
resource "aws_iam_role" "github_actions" {
  name = "github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub": "repo:org/repo:*"
          }
        }
      }
    ]
  })
}

# 5. CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cluster_cpu" {
  alarm_name          = "eks-cluster-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "cluster_cpu_utilization"
  namespace           = "AWS/EKS"
  period             = "300"
  statistic          = "Average"
  threshold          = "80"
  alarm_description  = "Alarm when CPU exceeds 80%"
  alarm_actions      = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = module.eks.cluster_name
  }
}
```

### GitOps Pipeline Setup
```hcl
# 1. Flux CD Installation
resource "helm_release" "flux" {
  name       = "flux"
  repository = "https://charts.fluxcd.io"
  chart      = "flux"
  namespace  = "flux-system"

  set {
    name  = "git.url"
    value = "ssh://git@github.com/org/repo"
  }

  depends_on = [module.eks]
}

# 2. ArgoCD Installation
resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  namespace  = "argocd"

  values = [
    file("${path.module}/argocd-values.yaml")
  ]

  depends_on = [module.eks]
}

# 3. External Secrets Operator
resource "helm_release" "external_secrets" {
  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  namespace  = "external-secrets"

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.external_secrets.arn
  }
}
```

## Common Integration Patterns

### EKS with AWS Load Balancer Controller
```hcl
# 1. Install AWS Load Balancer Controller
module "lb_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"

  role_name                              = "aws-load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.lb_role.iam_role_arn
  }
}

# 2. Example Ingress
resource "kubernetes_ingress_v1" "example" {
  metadata {
    name = "example-ingress"
    annotations = {
      "kubernetes.io/ingress.class"                = "alb"
      "alb.ingress.kubernetes.io/scheme"           = "internet-facing"
      "alb.ingress.kubernetes.io/target-type"      = "ip"
      "alb.ingress.kubernetes.io/certificate-arn"  = aws_acm_certificate.cert.arn
    }
  }

  spec {
    rule {
      host = "example.com"
      http {
        path {
          path = "/*"
          backend {
            service {
              name = "example-service"
              port {
                number = 80
              }
            }
          }
        }
      }
    }
  }
}
```

### Secrets Management with AWS Secrets Manager
```hcl
# 1. Create Secrets in AWS Secrets Manager
resource "aws_secretsmanager_secret" "app" {
  name = "app/production"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    db_password   = random_password.db.result
    api_key      = random_password.api.result
  })
}

# 2. External Secrets Configuration
resource "kubernetes_manifest" "secret_store" {
  manifest = {
    apiVersion = "external-secrets.io/v1beta1"
    kind       = "SecretStore"
    metadata = {
      name      = "aws-secret-store"
      namespace = "default"
    }
    spec = {
      provider = {
        aws = {
          service = "SecretsManager"
          region  = "us-west-2"
          auth = {
            jwt = {
              serviceAccountRef = {
                name = "external-secrets-sa"
              }
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_manifest" "external_secret" {
  manifest = {
    apiVersion = "external-secrets.io/v1beta1"
    kind       = "ExternalSecret"
    metadata = {
      name      = "app-secrets"
      namespace = "default"
    }
    spec = {
      refreshInterval = "1h"
      secretStoreRef = {
        name = "aws-secret-store"
        kind = "SecretStore"
      }
      target = {
        name = "app-secrets"
      }
      data = [
        {
          secretKey = "db_password"
          remoteRef = {
            key  = "app/production"
            property = "db_password"
          }
        },
        {
          secretKey = "api_key"
          remoteRef = {
            key  = "app/production"
            property = "api_key"
          }
        }
      ]
    }
  }
}
