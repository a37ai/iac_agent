---
tool: docker
category: containerization
version: "24.0"
topics:
  - containers
  - images
  - networking
---
# Docker Basic Operations

## Common Commands

### Container Management
```bash
# Run a container
docker run -d -p 80:80 nginx

# List containers
docker ps

# Stop container
docker stop container_id

# Remove container
docker rm container_id
```

## Common Issues and Solutions

### Error: Cannot connect to the Docker daemon
```error
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

Solution:
1. Start Docker service:
```bash
# Linux
sudo systemctl start docker

# Windows
net start com.docker.service
```

2. Add user to docker group:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Error: Port is already allocated
```error
Bind for 0.0.0.0:80 failed: port is already allocated
```

Solution:
1. Check used ports:
```bash
netstat -tulpn | grep 80
```

2. Use different port:
```bash
docker run -p 8080:80 nginx
```

### Error: No space left on device
```error
no space left on device
```

Solution:
1. Clean unused resources:
```bash
docker system prune -a
docker volume prune
```

2. Increase Docker storage:
```bash
# Check current usage
docker system df
```
