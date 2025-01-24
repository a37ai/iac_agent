---
tool: aws
category: containers
version: "2023-01-01"
topics:
  - ecs
  - containers
  - orchestration
---
# AWS ECS (Elastic Container Service)

## Common Operations

### Task Definition
```json
{
  "family": "web-app",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "nginx:latest",
      "memory": 256,
      "cpu": 256,
      "portMappings": [
        {
          "containerPort": 80,
          "hostPort": 80,
          "protocol": "tcp"
        }
      ]
    }
  ]
}
```

## Common Issues and Solutions

### Error: Service Unable to Place Task
```error
service web-app was unable to place a task because no container instance met all of its requirements
```

Solution:
1. Check capacity:
```bash
aws ecs describe-container-instances \
  --cluster your-cluster \
  --container-instances container-instance-id
```

2. Verify resource constraints:
- CPU units available
- Memory available
- Port availability

3. Check placement constraints:
```json
{
  "placementConstraints": [
    {
      "type": "memberOf",
      "expression": "attribute:ecs.instance-type =~ t2.*"
    }
  ]
}
```

### Error: Container Health Check Failed
```error
service web-app has not reached a steady state. tasks failed container health checks
```

Solution:
1. Check container logs:
```bash
aws ecs describe-container-instances \
  --cluster your-cluster \
  --container-instances container-instance-id
```

2. Configure health check:
```json
{
  "healthCheck": {
    "command": ["CMD-SHELL", "curl -f http://localhost/ || exit 1"],
    "interval": 30,
    "timeout": 5,
    "retries": 3
  }
}
```
