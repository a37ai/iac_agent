---
tool: datadog
category: monitoring
version: "7.0"
topics:
  - agent
  - integrations
  - metrics
---
# Datadog Agent Configuration

## Common Operations

### Agent Installation
```bash
# Linux
DD_AGENT_MAJOR_VERSION=7 DD_API_KEY=<API_KEY> \
DD_SITE="datadoghq.com" bash -c \
"$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh)"

# Docker
docker run -d \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc/:/host/proc/:ro \
  -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
  -e DD_API_KEY=<API_KEY> \
  -e DD_SITE="datadoghq.com" \
  datadog/agent:7
```

## Common Issues and Solutions

### Error: Agent Not Reporting
```error
Error: Datadog Agent is not reporting data
```

Solution:
1. Check agent status:
```bash
datadog-agent status
```

2. Verify API key:
```yaml
# datadog.yaml
api_key: <API_KEY>
site: datadoghq.com
```

3. Test connectivity:
```bash
datadog-agent health
```

### Error: Integration Failed
```error
Error: Integration 'xyz' failed to collect metrics
```

Solution:
1. Check integration config:
```yaml
# conf.d/integration.yaml
init_config:
instances:
  - host: localhost
    port: 8080
```

2. Reload agent:
```bash
datadog-agent reload
```

### Error: Custom Metrics
```error
Error: Custom metric submission failed
```

Solution:
1. Check DogStatsD:
```bash
netstat -an | grep 8125
```

2. Configure custom metrics:
```python
from datadog import initialize, statsd

initialize(api_key='<API_KEY>')
statsd.increment('custom.metric')
```

3. Verify metric:
```bash
datadog-agent check <integration_name>
```
