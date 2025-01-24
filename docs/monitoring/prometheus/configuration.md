---
tool: prometheus
category: monitoring
version: "2.45"
topics:
  - metrics
  - alerting
  - scraping
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md#monitoring
    description: "Monitoring Kubernetes clusters"
  - path: /monitoring/grafana/dashboards.md#prometheus-datasource
    description: "Using Prometheus as Grafana data source"
  - path: /monitoring/datadog/agent.md#prometheus-integration
    description: "Integrating Prometheus with Datadog"
  - path: /cicd/github_actions/workflows.md#monitoring
    description: "Monitoring CI/CD pipelines"
  - path: /monitoring/elk/setup.md#metrics-integration
    description: "Integrating metrics with ELK Stack"
---
# Prometheus Configuration

## Basic Configuration

### prometheus.yml
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

## Common Issues and Solutions

### Error: Failed to reload config
```error
Error reloading config: yaml: line X: mapping values are not allowed in this context
```

Solution:
1. Validate YAML syntax:
```bash
promtool check config prometheus.yml
```

2. Check indentation and format

### Error: Scrape failed
```error
scrape_samples_scraped{instance="target"} 0
```

Solution:
1. Check target availability:
```bash
curl http://target-host:port/metrics
```

2. Verify network access:
```bash
telnet target-host port
```

3. Check authentication:
```yaml
scrape_configs:
  - job_name: 'secure-app'
    basic_auth:
      username: 'user'
      password: 'pass'
```

### Error: Storage issues
```error
storage operation failed
```

Solution:
1. Check disk space:
```bash
df -h /prometheus
```

2. Adjust retention:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  retention_time: 15d
```

3. Clean old data:
```bash
prometheus clean
```
