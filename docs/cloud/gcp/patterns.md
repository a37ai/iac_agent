---
tool: gcp
category: cloud
version: "2024-01"
topics:
  - patterns
  - architecture
  - security
  - networking
related_topics:
  - path: /iac/terraform/gcp_provider.md
    description: "Managing GCP with Terraform"
  - path: /containers/kubernetes/advanced_patterns.md#gke
    description: "GKE deployment patterns"
  - path: /monitoring/stackdriver/configuration.md
    description: "GCP monitoring with Stackdriver"
  - path: /security/cloud/gcp.md
    description: "GCP security best practices"
---

# Google Cloud Platform Patterns

## Complex Multi-Tool Workflows

### Complete Cloud-Native Architecture
```yaml
# terraform/main.tf
provider "google" {
  project = var.project_id
  region  = var.region
}

# VPC and Networking
resource "google_compute_network" "vpc" {
  name                    = "${var.project_id}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.project_id}-subnet"
  ip_cidr_range = "10.0.0.0/20"
  network       = google_compute_network.vpc.id
  region        = var.region

  secondary_ip_range {
    range_name    = "gke-pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "gke-services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# GKE Cluster
resource "google_container_cluster" "primary" {
  name     = "${var.project_id}-gke"
  location = var.region

  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "gke-pods"
    services_secondary_range_name = "gke-services"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }
}

resource "google_container_node_pool" "primary_nodes" {
  name       = "${google_container_cluster.primary.name}-node-pool"
  location   = var.region
  cluster    = google_container_cluster.primary.name
  node_count = var.gke_num_nodes

  node_config {
    oauth_scopes = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
      "https://www.googleapis.com/auth/devstorage.read_only"
    ]

    labels = {
      env = var.project_id
    }

    machine_type = "n1-standard-2"
    disk_size_gb = 100
    disk_type    = "pd-standard"

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }
}

# Cloud SQL
resource "google_sql_database_instance" "main" {
  name             = "${var.project_id}-db"
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    backup_configuration {
      enabled    = true
      start_time = "02:00"
    }
  }

  deletion_protection = true
}

# Cloud Storage
resource "google_storage_bucket" "static" {
  name          = "${var.project_id}-static"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

# Cloud Pub/Sub
resource "google_pubsub_topic" "events" {
  name = "events"
}

resource "google_pubsub_subscription" "events_sub" {
  name  = "events-sub"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 20

  retry_policy {
    minimum_backoff = "10s"
  }

  enable_message_ordering = true
}

# IAM and Security
resource "google_service_account" "gke_sa" {
  account_id   = "gke-sa"
  display_name = "GKE Service Account"
}

resource "google_project_iam_member" "gke_sa_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_sa.email}"
}
```

### Cloud Functions and Event-Driven Architecture
```python
# functions/main.py
from google.cloud import storage
from google.cloud import pubsub_v1
import functions_framework
import base64
import json

@functions_framework.cloud_event
def process_storage_event(cloud_event):
    data = cloud_event.data

    if "name" not in data:
        return

    file_name = data["name"]
    bucket_name = data["bucket"]

    # Process the file
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Read and process
    content = blob.download_as_string()
    result = process_content(content)

    # Publish result
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(
        "your-project-id", 
        "events"
    )

    message = {
        "file": file_name,
        "result": result
    }

    publisher.publish(
        topic_path,
        json.dumps(message).encode("utf-8"),
        origin="storage-function",
        type="file-processed"
    )

# functions/requirements.txt
google-cloud-storage==2.10.0
google-cloud-pubsub==2.18.0
functions-framework==3.4.0
```

## Integration Patterns

### Hybrid Connectivity
```hcl
# terraform/vpn.tf
resource "google_compute_ha_vpn_gateway" "ha_gateway" {
  name    = "ha-vpn-gateway"
  network = google_compute_network.vpc.id
  region  = var.region
}

resource "google_compute_external_vpn_gateway" "external_gateway" {
  name            = "external-gateway"
  redundancy_type = "TWO_IPS_REDUNDANCY"
  description     = "External VPN Gateway"

  interface {
    id         = 0
    ip_address = var.external_vpn_ip_1
  }

  interface {
    id         = 1
    ip_address = var.external_vpn_ip_2
  }
}

resource "google_compute_vpn_tunnel" "tunnel1" {
  name                  = "ha-vpn-tunnel1"
  region                = var.region
  vpn_gateway          = google_compute_ha_vpn_gateway.ha_gateway.id
  peer_external_gateway = google_compute_external_vpn_gateway.external_gateway.id
  peer_external_gateway_interface = 0
  shared_secret        = var.vpn_shared_secret
  router               = google_compute_router.router.id

  vpn_gateway_interface = 0
}

resource "google_compute_router" "router" {
  name    = "ha-vpn-router"
  region  = var.region
  network = google_compute_network.vpc.id

  bgp {
    asn = 64514
  }
}
```

### Load Balancing and CDN
```hcl
# terraform/lb.tf
resource "google_compute_global_address" "default" {
  name = "global-lb-ip"
}

resource "google_compute_global_forwarding_rule" "default" {
  name                  = "global-rule"
  ip_protocol          = "TCP"
  load_balancing_scheme = "EXTERNAL"
  port_range           = "80"
  target               = google_compute_target_http_proxy.default.id
  ip_address           = google_compute_global_address.default.id
}

resource "google_compute_target_http_proxy" "default" {
  name    = "target-proxy"
  url_map = google_compute_url_map.default.id
}

resource "google_compute_url_map" "default" {
  name            = "url-map"
  default_service = google_compute_backend_service.default.id

  host_rule {
    hosts        = ["*"]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_service.default.id
  }
}

resource "google_compute_backend_service" "default" {
  name                  = "backend-service"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL"
  timeout_sec           = 10
  health_checks         = [google_compute_health_check.default.id]
  backend {
    group = google_compute_instance_group_manager.default.instance_group
  }
  enable_cdn = true

  cdn_policy {
    cache_mode = "CACHE_ALL_STATIC"
    client_ttl = 3600
    default_ttl = 3600
    max_ttl     = 86400
  }
}
```

## Common Issues and Solutions

### Error: GKE Cluster Creation
```error
Error creating cluster: Insufficient regional quota to satisfy request
```

Solution:
1. Check quota usage:
```bash
gcloud compute regions describe REGION \
  --format="table(quotas.metric,quotas.limit,quotas.usage)"
```

2. Request quota increase:
```bash
gcloud quota update --project=PROJECT_ID \
  --quota_user=USER \
  --consumer_project_id=PROJECT_ID \
  --service=compute.googleapis.com \
  --metric=METRIC \
  --limit=NEW_LIMIT \
  --region=REGION
```

### Error: VPC Peering
```error
Error establishing VPC peering: overlapping IP ranges
```

Solution:
1. Check IP ranges:
```bash
gcloud compute networks subnets list \
  --project=PROJECT_ID \
  --format="table(name,network,region,ipCidrRange)"
```

2. Update subnet ranges:
```hcl
resource "google_compute_subnetwork" "subnet" {
  name          = "custom-subnet"
  ip_cidr_range = "192.168.1.0/24"  # Non-overlapping range
  network       = google_compute_network.vpc.id
}
```

### Error: Cloud SQL Connectivity
```error
Cannot connect to Cloud SQL instance
```

Solution:
1. Check private service access:
```bash
gcloud services vpc-peerings list \
  --network=VPC_NAME
```

2. Configure private IP:
```hcl
resource "google_compute_global_address" "private_ip_address" {
  name          = "private-ip-address"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}
```
