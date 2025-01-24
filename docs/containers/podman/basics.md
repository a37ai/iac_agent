---
tool: podman
category: containerization
version: "4.0"
topics:
  - containers
  - pods
  - images
---
# Podman Basic Operations

## Common Operations

### Container Management
```bash
# Run container
podman run -d -p 80:80 nginx

# List containers
podman ps

# Pod operations
podman pod create my-pod
podman run -dt --pod my-pod nginx
```

## Common Issues and Solutions

### Error: Permission Denied
```error
Error: cannot open database "containers_db": permission denied
```

Solution:
1. Fix permissions:
```bash
podman system reset
podman system migrate
```

2. Run rootless:
```bash
podman unshare
podman run --userns=keep-id nginx
```

### Error: Image Pull Failed
```error
Error: unable to pull image: manifest unknown
```

Solution:
1. Check registry:
```bash
podman login registry.example.com
```

2. Update image:
```bash
podman pull --tls-verify=false nginx
```

3. Configure registries:
```bash
# /etc/containers/registries.conf
[registries.search]
registries = ['docker.io', 'quay.io']
```

### Error: Network Issues
```error
Error: unable to start container: network not found
```

Solution:
1. List networks:
```bash
podman network ls
```

2. Create network:
```bash
podman network create my-net
```

3. Connect container:
```bash
podman run --network my-net nginx
```
