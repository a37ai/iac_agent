---
tool: nomad
category: containers
version: "1.7"
topics:
  - orchestration
  - scheduling
  - deployment
  - networking
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md
    description: "Comparing Nomad and Kubernetes patterns"
  - path: /monitoring/prometheus/configuration.md#nomad
    description: "Monitoring Nomad clusters"
  - path: /security/vault/configuration.md#nomad
    description: "Integrating Nomad with Vault"
  - path: /networking/consul/configuration.md#nomad
    description: "Service discovery with Consul"
---

# Nomad Orchestration Patterns

## Complex Multi-Tool Workflows

### Complete Microservices Platform
```hcl
# job.nomad
job "platform" {
  datacenters = ["dc1"]
  type = "service"

  group "frontend" {
    count = 3

    network {
      mode = "bridge"
      port "http" {
        to = 80
      }
    }

    service {
      name = "frontend"
      port = "http"
      
      connect {
        sidecar_service {
          proxy {
            upstreams {
              destination_name = "api"
              local_bind_port = 8080
            }
          }
        }
      }

      check {
        type     = "http"
        path     = "/health"
        interval = "10s"
        timeout  = "2s"
      }
    }

    task "nginx" {
      driver = "docker"

      config {
        image = "nginx:latest"
        ports = ["http"]
        volumes = [
          "local/nginx.conf:/etc/nginx/nginx.conf",
          "local/html:/usr/share/nginx/html"
        ]
      }

      template {
        data = <<EOF
events {
    worker_connections 1024;
}
http {
    upstream backend {
        server {{ env "NOMAD_UPSTREAM_ADDR_api" }};
    }
    server {
        listen 80;
        location / {
            root /usr/share/nginx/html;
            index index.html;
        }
        location /api {
            proxy_pass http://backend;
        }
    }
}
EOF
        destination = "local/nginx.conf"
      }

      resources {
        cpu    = 500
        memory = 256
      }
    }
  }

  group "api" {
    count = 5

    update {
      max_parallel     = 1
      canary          = 1
      auto_revert     = true
      auto_promote    = false
      health_check    = "checks"
      min_healthy_time = "10s"
      healthy_deadline = "5m"
    }

    network {
      mode = "bridge"
      port "http" {
        to = 8080
      }
    }

    service {
      name = "api"
      port = "http"
      
      connect {
        sidecar_service {
          proxy {
            upstreams {
              destination_name = "database"
              local_bind_port = 5432
            }
          }
        }
      }

      check {
        type     = "http"
        path     = "/health"
        interval = "10s"
        timeout  = "2s"
      }
    }

    task "api" {
      driver = "docker"

      vault {
        policies = ["api-prod"]
      }

      config {
        image = "api:latest"
        ports = ["http"]
      }

      template {
        data = <<EOF
DATABASE_URL="postgresql://{{ with secret "database/creds/api" }}{{ .Data.username }}:{{ .Data.password }}@{{ env "NOMAD_UPSTREAM_ADDR_database" }}/myapp{{ end }}"
REDIS_URL="redis://{{ env "NOMAD_UPSTREAM_ADDR_redis" }}"
EOF
        destination = "secrets/config.env"
        env         = true
      }

      resources {
        cpu    = 1000
        memory = 512
      }
    }
  }

  group "database" {
    count = 1

    network {
      mode = "bridge"
      port "db" {
        static = 5432
        to     = 5432
      }
    }

    volume "postgres" {
      type      = "host"
      source    = "postgres"
      read_only = false
    }

    service {
      name = "database"
      port = "db"

      check {
        type     = "tcp"
        interval = "10s"
        timeout  = "2s"
      }
    }

    task "postgres" {
      driver = "docker"

      config {
        image = "postgres:14"
        ports = ["db"]
      }

      env {
        POSTGRES_USER     = "postgres"
        POSTGRES_PASSWORD = "postgres"
        POSTGRES_DB       = "myapp"
      }

      volume_mount {
        volume      = "postgres"
        destination = "/var/lib/postgresql/data"
        read_only   = false
      }

      resources {
        cpu    = 1000
        memory = 1024
      }
    }
  }
}
```

### Advanced Scheduling
```hcl
# custom-scheduler.nomad
job "custom-scheduler" {
  datacenters = ["dc1"]
  type = "system"

  constraint {
    attribute = "${attr.cpu.arch}"
    value     = "amd64"
  }

  constraint {
    attribute = "${meta.storage_type}"
    value     = "ssd"
  }

  spread {
    attribute = "${node.datacenter}"
    weight    = 100
    target "us-east" {
      percent = 60
    }
    target "us-west" {
      percent = 40
    }
  }

  affinity {
    attribute = "${meta.instance_type}"
    value     = "m5.large"
    weight    = 50
  }

  group "workers" {
    count = 10

    reschedule {
      attempts       = 3
      interval      = "1h"
      delay         = "30s"
      delay_function = "exponential"
      max_delay      = "1h"
      unlimited     = false
    }

    migrate {
      max_parallel     = 3
      health_check     = "checks"
      min_healthy_time = "10s"
      healthy_deadline = "5m"
    }

    task "worker" {
      driver = "docker"

      config {
        image = "worker:latest"
      }

      resources {
        cpu    = 500
        memory = 256
      }

      scaling {
        enabled = true
        min     = 5
        max     = 20
        policy {
          cooldown            = "2m"
          evaluation_interval = "1m"

          check "cpu" {
            source = "prometheus"
            query  = "avg(nomad_client_allocs_cpu_total_percent{task_group=\"workers\"})"
            
            strategy "target-value" {
              target = 70
            }
          }
        }
      }
    }
  }
}
```

## Integration Patterns

### Service Mesh with Consul
```hcl
# service-mesh.nomad
job "service-mesh" {
  datacenters = ["dc1"]

  group "api" {
    network {
      mode = "bridge"
      port "http" {
        to = 8080
      }
    }

    service {
      name = "api"
      port = "http"

      connect {
        sidecar_service {
          proxy {
            config {
              protocol = "http"
            }
            expose {
              path {
                path            = "/api"
                protocol        = "http"
                local_path_port = 8080
                listener_port   = "expose"
              }
            }
            upstreams {
              destination_name = "database"
              local_bind_port  = 5432
            }
          }
        }
      }
    }

    task "api" {
      driver = "docker"

      config {
        image = "api:latest"
      }

      env {
        CONSUL_HTTP_ADDR = "http://${NOMAD_IP_http}:8500"
      }
    }
  }
}
```

### Dynamic Secrets with Vault
```hcl
# secrets.nomad
job "secrets" {
  datacenters = ["dc1"]

  group "app" {
    task "app" {
      driver = "docker"

      vault {
        policies = ["app"]
        change_mode = "signal"
        change_signal = "SIGUSR1"
      }

      template {
        data = <<EOF
{{ with secret "database/creds/app" }}
DB_USER="{{ .Data.username }}"
DB_PASS="{{ .Data.password }}"
{{ end }}

{{ with secret "aws/creds/app" }}
AWS_ACCESS_KEY_ID="{{ .Data.access_key }}"
AWS_SECRET_ACCESS_KEY="{{ .Data.secret_key }}"
{{ end }}
EOF
        destination = "secrets/config.env"
        env = true
      }

      config {
        image = "app:latest"
      }
    }
  }
}
```

## Common Issues and Solutions

### Error: Task Failed to Start
```error
Task 'redis' failed to start: Failed to find task ip
```

Solution:
1. Check network configuration:
```hcl
network {
  mode = "bridge"
  port "redis" {
    to = 6379
  }
}
```

2. Verify driver availability:
```bash
nomad node status -self
nomad node config -json
```

### Error: Resource Constraints
```error
Placement failed: no nodes satisfied constraints
```

Solution:
1. Check node resources:
```bash
nomad node status -stats
```

2. Adjust resource requirements:
```hcl
resources {
  cpu    = 500  # MHz
  memory = 256  # MB
  
  device "nvidia/gpu" {
    count = 0
  }
}
```

### Error: Service Discovery
```error
Service registration failed
```

Solution:
1. Verify Consul connection:
```hcl
service {
  name = "api"
  port = "http"
  tags = ["v1"]
  
  check {
    type     = "http"
    path     = "/health"
    interval = "10s"
    timeout  = "2s"
  }
}
```

2. Check Consul agent:
```bash
consul members
consul catalog services
```
