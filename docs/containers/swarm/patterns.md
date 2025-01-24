---
tool: docker_swarm
category: containers
version: "20.10"
topics:
  - orchestration
  - deployment
  - networking
  - security
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md
    description: "Kubernetes vs Swarm patterns"
  - path: /monitoring/prometheus/configuration.md#swarm
    description: "Monitoring Swarm clusters"
  - path: /cicd/github_actions/workflows.md#swarm-deployment
    description: "Deploying to Swarm with GitHub Actions"
  - path: /security/container/scanning.md#swarm
    description: "Container security in Swarm"
---

# Docker Swarm Orchestration Patterns

## Complex Multi-Tool Workflows

### Complete Microservices Stack
```yaml
# docker-compose.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.9
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.swarmMode=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/certificates/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-certificates:/certificates
    networks:
      - traefik-public
    deploy:
      placement:
        constraints:
          - node.role == manager
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.dashboard.rule=Host(`traefik.example.com`)"
        - "traefik.http.routers.dashboard.service=api@internal"
        - "traefik.http.routers.dashboard.middlewares=auth"
        - "traefik.http.middlewares.auth.basicauth.users=admin:$$apr1$$xyz123"

  api:
    image: myapp/api:latest
    environment:
      - DATABASE_URL=postgres://user:pass@db:5432/myapp
      - REDIS_URL=redis://cache:6379
      - NODE_ENV=production
    networks:
      - backend
      - traefik-public
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
      rollback_config:
        parallelism: 1
        delay: 5s
        order: stop-first
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.api.rule=Host(`api.example.com`)"
        - "traefik.http.services.api.loadbalancer.server.port=3000"
        - "traefik.http.routers.api.middlewares=cors,ratelimit"
        - "traefik.http.middlewares.cors.headers.accesscontrolallowmethods=GET,POST,PUT,DELETE,OPTIONS"
        - "traefik.http.middlewares.ratelimit.ratelimit.average=100"
        - "traefik.http.middlewares.ratelimit.ratelimit.burst=50"

  db:
    image: postgres:14-alpine
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - backend
    deploy:
      placement:
        constraints:
          - node.labels.db == true
      resources:
        limits:
          cpus: '1'
          memory: 2G
      labels:
        - "backup.enabled=true"
        - "backup.schedule=0 0 * * *"

  cache:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - cache-data:/data
    networks:
      - backend
    deploy:
      placement:
        constraints:
          - node.labels.cache == true
      update_config:
        parallelism: 1
        delay: 10s
        order: stop-first

networks:
  traefik-public:
    driver: overlay
    attachable: true
  backend:
    driver: overlay
    attachable: false
    driver_opts:
      encrypted: "true"

volumes:
  traefik-certificates:
    driver: local
  db-data:
    driver: local
  cache-data:
    driver: local
```

### High Availability Setup
```bash
# swarm-setup.sh
#!/bin/bash

# Initialize Swarm cluster
docker swarm init --advertise-addr eth0

# Create required networks
docker network create --driver overlay traefik-public
docker network create --driver overlay --attachable backend

# Label nodes
docker node update --label-add db=true node1
docker node update --label-add cache=true node2
docker node update --label-add app=true node3

# Deploy stack
docker stack deploy -c docker-compose.yml myapp

# Configure backups
cat > /etc/cron.d/swarm-backup << EOF
0 0 * * * root docker run --rm \
  --volumes-from $(docker ps -q -f name=db) \
  -v /backup:/backup \
  postgres:14-alpine \
  sh -c 'pg_dump -U $POSTGRES_USER $POSTGRES_DB > /backup/dump_\$(date +%Y%m%d).sql'
EOF
```

## Integration Patterns

### Service Discovery and Load Balancing
```yaml
# traefik-config.yml
version: '3.8'

services:
  api_v1:
    image: myapp/api:1.0
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.apiv1.rule=Host(`api.example.com`) && PathPrefix(`/v1`)"
        - "traefik.http.services.apiv1.loadbalancer.server.port=3000"
        - "traefik.http.routers.apiv1.middlewares=strip-prefix"
        - "traefik.http.middlewares.strip-prefix.stripprefix.prefixes=/v1"

  api_v2:
    image: myapp/api:2.0
    deploy:
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.apiv2.rule=Host(`api.example.com`) && PathPrefix(`/v2`)"
        - "traefik.http.services.apiv2.loadbalancer.server.port=3000"
        - "traefik.http.routers.apiv2.middlewares=strip-prefix"
        - "traefik.http.middlewares.strip-prefix.stripprefix.prefixes=/v2"
```

### Secrets Management
```yaml
# secrets.yml
version: '3.8'

services:
  api:
    secrets:
      - source: api_key
        target: /run/secrets/api_key
        mode: 0400
      - source: ssl_cert
        target: /run/secrets/ssl_cert
        mode: 0400
    command: ["sh", "-c", "API_KEY=$(cat /run/secrets/api_key) ./start.sh"]

secrets:
  api_key:
    external: true
  ssl_cert:
    external: true

# Create secrets
echo "my-secret-api-key" | docker secret create api_key -
cat ssl_cert.pem | docker secret create ssl_cert -
```

## Common Issues and Solutions

### Error: Service Not Starting
```error
Service failed to start: task: non-zero exit (1)
```

Solution:
1. Check service logs:
```bash
docker service logs <service_name>
```

2. Verify resource constraints:
```bash
docker service update \
  --limit-cpu 0.5 \
  --limit-memory 512M \
  <service_name>
```

### Error: Network Connectivity
```error
Services cannot communicate with each other
```

Solution:
1. Check network configuration:
```bash
docker network inspect <network_name>
```

2. Verify service attachment:
```bash
docker service update \
  --network-add backend \
  <service_name>
```

### Error: Load Balancing Issues
```error
Requests not being distributed evenly
```

Solution:
1. Check service replicas:
```bash
docker service ls
docker service scale <service_name>=3
```

2. Verify Traefik configuration:
```yaml
deploy:
  labels:
    - "traefik.http.services.myapp.loadbalancer.sticky=true"
    - "traefik.http.services.myapp.loadbalancer.sticky.cookie.name=sticky"
```
