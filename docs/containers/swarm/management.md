---
tool: docker_swarm
category: orchestration
version: "24.0"
topics:
  - swarm
  - services
  - nodes
---
# Docker Swarm Management

## Common Operations

### Swarm Setup
```bash
# Initialize swarm
docker swarm init --advertise-addr <MANAGER-IP>

# Join swarm
docker swarm join --token <TOKEN> <MANAGER-IP>:2377

# Create service
docker service create --name web --replicas 3 nginx
```

## Common Issues and Solutions

### Error: Unable to Initialize Swarm
```error
Error response from daemon: could not choose an IP address to advertise
```

Solution:
1. Specify interface:
```bash
docker swarm init --advertise-addr eth0
```

2. Check network:
```bash
ip addr show
```

### Error: Node Communication
```error
Error response from daemon: rpc error: code = Unavailable desc = connection error
```

Solution:
1. Check ports:
```bash
netstat -tulpn | grep LISTEN
```

2. Configure firewall:
```bash
# Open required ports
firewall-cmd --permanent --add-port=2377/tcp
firewall-cmd --permanent --add-port=7946/tcp
firewall-cmd --permanent --add-port=7946/udp
firewall-cmd --permanent --add-port=4789/udp
```

### Error: Service Deployment
```error
service web update: update out of sequence
```

Solution:
1. Force update:
```bash
docker service update --force web
```

2. Check service logs:
```bash
docker service logs web
```

3. Scale service:
```bash
docker service scale web=5
```
