---
tool: terraform
category: providers
version: "4.0"
topics:
  - gcp
  - provider configuration
  - authentication
  - resources
---
# Google Cloud Provider Configuration in Terraform

## Provider Setup

### Basic Configuration
```hcl
provider "google" {
  project     = "your-project-id"
  region      = "us-central1"
  zone        = "us-central1-a"
  credentials = file("path/to/service-account.json")
}
```

### Workload Identity Federation
```hcl
provider "google" {
  project               = "your-project-id"
  region                = "us-central1"
  zone                  = "us-central1-a"
  access_token          = data.google_service_account_access_token.default.access_token
  impersonate_service_account = "sa-name@project-id.iam.gserviceaccount.com"
}

data "google_service_account_access_token" "default" {
  target_service_account = "sa-name@project-id.iam.gserviceaccount.com"
  scopes                = ["cloud-platform"]
  lifetime              = "3600s"
}
```

## Common Resources

### GKE Cluster
```hcl
resource "google_container_cluster" "primary" {
  name     = "my-gke-cluster"
  location = "us-central1"

  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }
}

resource "google_container_node_pool" "primary_preemptible_nodes" {
  name       = "my-node-pool"
  location   = "us-central1"
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    preemptible  = true
    machine_type = "e2-medium"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}
```

### Cloud SQL Instance
```hcl
resource "google_sql_database_instance" "main" {
  name             = "main-instance"
  database_version = "POSTGRES_13"
  region           = "us-central1"

  settings {
    tier = "db-f1-micro"
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "allow-all"
        value = "0.0.0.0/0"
      }
    }

    backup_configuration {
      enabled = true
      start_time = "03:00"
    }
  }

  deletion_protection = true
}
```

## Common Issues and Solutions

### Error: Service Account Permissions
```error
Error: Error creating Cluster: googleapi: Error 403: Required "container.clusters.create" permission
```

Solution:
1. Check IAM roles:
```bash
gcloud projects get-iam-policy PROJECT_ID
```

2. Add required roles:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SA_NAME@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/container.admin"
```

3. Update service account:
```hcl
resource "google_service_account_iam_binding" "admin-account-iam" {
  service_account_id = google_service_account.kubernetes.name
  role               = "roles/container.admin"

  members = [
    "serviceAccount:${google_service_account.kubernetes.email}",
  ]
}
```

### Error: Quota Exceeded
```error
Error: Error creating instance: googleapi: Error 403: Quota 'CPUS' exceeded
```

Solution:
1. Check quota:
```bash
gcloud compute project-info describe --project PROJECT_ID
```

2. Request quota increase:
```bash
# Via Google Cloud Console
# IAM & Admin > Quotas > Select resource > EDIT QUOTAS
```

3. Use smaller instance:
```hcl
resource "google_compute_instance" "vm_instance" {
  name         = "terraform-instance"
  machine_type = "e2-micro"  # Instead of larger instance
}
```

## Complex Workflows

### Multi-Regional Load Balancing with Cloud CDN
```hcl
# VPC and Subnet Configuration
resource "google_compute_network" "vpc" {
  name                    = "my-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  for_each = {
    us-central1 = "10.0.1.0/24"
    us-east1    = "10.0.2.0/24"
  }

  name          = "subnet-${each.key}"
  ip_cidr_range = each.value
  region        = each.key
  network       = google_compute_network.vpc.id
}

# Instance Template
resource "google_compute_instance_template" "default" {
  name        = "web-template"
  description = "Web server template"

  machine_type = "e2-medium"

  disk {
    source_image = "debian-cloud/debian-10"
    auto_delete  = true
    boot         = true
  }

  network_interface {
    network = google_compute_network.vpc.name
    access_config {
      # Ephemeral IP
    }
  }

  metadata_startup_script = "apt-get update && apt-get install -y nginx"
}

# Regional Instance Groups
resource "google_compute_region_instance_group_manager" "mig" {
  for_each = toset(["us-central1", "us-east1"])

  name = "mig-${each.key}"
  region = each.key
  base_instance_name = "web"
  target_size = 2

  version {
    instance_template = google_compute_instance_template.default.id
  }

  named_port {
    name = "http"
    port = 80
  }
}

# Global Load Balancer
resource "google_compute_global_forwarding_rule" "default" {
  name       = "global-rule"
  target     = google_compute_target_http_proxy.default.id
  port_range = "80"
}

resource "google_compute_target_http_proxy" "default" {
  name    = "target-proxy"
  url_map = google_compute_url_map.default.id
}

resource "google_compute_url_map" "default" {
  name            = "url-map"
  default_service = google_compute_backend_service.default.id
}

resource "google_compute_backend_service" "default" {
  name        = "backend-service"
  protocol    = "HTTP"
  timeout_sec = 10
  enable_cdn  = true

  dynamic "backend" {
    for_each = google_compute_region_instance_group_manager.mig
    content {
      group = backend.value.instance_group
    }
  }

  health_checks = [google_compute_health_check.default.id]
}

resource "google_compute_health_check" "default" {
  name               = "health-check"
  check_interval_sec = 5
  timeout_sec        = 5

  http_health_check {
    port = 80
  }
}

# Cloud CDN
resource "google_compute_backend_service" "cdn_service" {
  name        = "cdn-service"
  protocol    = "HTTP"
  timeout_sec = 10
  enable_cdn  = true

  dynamic "backend" {
    for_each = google_compute_region_instance_group_manager.mig
    content {
      group = backend.value.instance_group
    }
  }

  cdn_policy {
    cache_mode = "CACHE_ALL_STATIC"
    default_ttl = 3600
    client_ttl  = 3600
    max_ttl     = 86400
  }
}
```
