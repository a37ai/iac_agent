---
tool: datadog
category: monitoring
version: "7.0"
topics:
  - integrations
  - metrics
  - logs
  - apm
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md#monitoring
    description: "Kubernetes monitoring with Datadog"
  - path: /monitoring/prometheus/configuration.md#datadog
    description: "Prometheus integration with Datadog"
  - path: /cicd/github_actions/workflows.md#monitoring
    description: "CI/CD monitoring with Datadog"
  - path: /iac/terraform/datadog_provider.md
    description: "Managing Datadog with Terraform"
---

# Datadog Integration Patterns

## Complex Multi-Tool Workflows

### Complete Kubernetes Monitoring
```yaml
# datadog-values.yaml
datadog:
  clusterName: production-cluster
  logs:
    enabled: true
    containerCollectAll: true
  apm:
    enabled: true
    hostPortConfig:
      enabled: true
      port: 8126
  processAgent:
    enabled: true
    processCollection: true
  systemProbe:
    enabled: true
    enableTCPQueueLength: true
    enableOOMKill: true
  security:
    runtime:
      enabled: true
  networkMonitoring:
    enabled: true
  orchestratorExplorer:
    enabled: true
  kubeStateMetricsCore:
    enabled: true
  clusterChecks:
    enabled: true
  admissionController:
    enabled: true
    mutateUnlabelled: true
  containerExclude: "kube_namespace:kube-system"
  tolerations:
    - operator: Exists
  kubelet:
    tlsVerify: false
  dogstatsd:
    useHostPort: true
    nonLocalTraffic: true
    originDetection: true
  env:
    - name: DD_APM_NON_LOCAL_TRAFFIC
      value: "true"
    - name: DD_LOGS_CONFIG_CONTAINER_COLLECT_ALL
      value: "true"
    - name: DD_CONTAINER_EXCLUDE_LOGS
      value: "name:datadog-agent"

# custom-metrics.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datadog-custom-metrics
data:
  conf.yaml: |
    init_config:
    instances:
      - min_collection_interval: 60
        custom_queries:
          - query: "SELECT count(*) FROM users WHERE created_at > NOW() - INTERVAL '1 day'"
            metric: "app.users.new_count"
            type: "gauge"
          - query: "SELECT avg(duration) FROM transactions WHERE status = 'completed'"
            metric: "app.transactions.avg_duration"
            type: "gauge"
```

### APM and Distributed Tracing
```python
# app/tracing.py
from ddtrace import patch_all, tracer
from ddtrace.propagation.http import HTTPPropagator

patch_all()

@tracer.wrap(service="payment-service")
def process_payment(payment_id):
    with tracer.trace("payment.processing", service="payment-service") as span:
        span.set_tag("payment.id", payment_id)
        span.set_tag("payment.type", "credit_card")
        
        # Process payment logic
        result = payment_gateway.process(payment_id)
        
        span.set_tag("payment.status", result.status)
        return result

# app/middleware.py
from ddtrace import tracer
from opentelemetry.propagate import extract, inject
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

class TracingMiddleware:
    def __init__(self, app):
        self.app = app
        self.propagator = TraceContextTextMapPropagator()

    async def __call__(self, scope, receive, send):
        headers = dict(scope["headers"])
        context = extract(headers)
        
        with tracer.trace("http.request") as span:
            span.set_tag("http.url", scope["path"])
            span.set_tag("http.method", scope["method"])
            
            response = await self.app(scope, receive, send)
            
            span.set_tag("http.status_code", response.status_code)
            return response
```

### Log Management and Analytics
```yaml
# datadog-logging.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datadog-logging-config
data:
  datadog.yaml: |
    logs:
      - type: file
        path: /var/log/app/*.log
        service: myapp
        source: python
        log_processing_rules:
          - type: multi_line
            pattern: \d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}
            name: new_log_start_pattern
          - type: mask_sequences
            pattern: ((?:password|token|key)["']:\s*["'][^"']+["'])
            replace_placeholder: "**********"
      - type: docker
        service: nginx
        source: nginx
        log_processing_rules:
          - type: exclude_at_match
            pattern: healthcheck
      - type: tcp
        port: 10514
        service: syslog
        source: syslog

# app/logging.py
import logging
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi

def setup_logging():
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        handlers=[
            DDHandler(
                api_key='<DD_API_KEY>',
                app_key='<DD_APP_KEY>',
                service='myapp',
                source='python',
                tags=['env:prod', 'team:backend']
            )
        ]
    )

class DDHandler(logging.Handler):
    def __init__(self, api_key, app_key, service, source, tags):
        super().__init__()
        configuration = Configuration()
        configuration.api_key['apiKeyAuth'] = api_key
        configuration.api_key['appKeyAuth'] = app_key
        self.api_client = ApiClient(configuration)
        self.logs_api = LogsApi(self.api_client)
        self.service = service
        self.source = source
        self.tags = tags

    def emit(self, record):
        try:
            log_entry = {
                'message': self.format(record),
                'service': self.service,
                'ddsource': self.source,
                'ddtags': ','.join(self.tags),
                'hostname': platform.node(),
                'status': record.levelname.lower(),
            }
            self.logs_api.submit_log(body=[log_entry])
        except Exception:
            self.handleError(record)
```

## Integration Patterns

### Infrastructure Monitoring
```yaml
# terraform/datadog.tf
resource "datadog_monitor" "high_cpu" {
  name               = "High CPU Usage"
  type               = "metric alert"
  message           = "CPU usage is above 80% on {{host.name}}"
  query             = "avg(last_5m):avg:system.cpu.user{*} by {host} > 80"
  
  monitor_thresholds {
    warning         = 70
    critical        = 80
  }

  notify_no_data    = true
  renotify_interval = 60

  tags = ["team:platform", "severity:high"]
}

resource "datadog_dashboard" "infrastructure" {
  title       = "Infrastructure Overview"
  description = "Key infrastructure metrics"
  layout_type = "ordered"

  widget {
    timeseries_definition {
      title = "CPU Usage by Host"
      request {
        q = "avg:system.cpu.user{*} by {host}"
        display_type = "line"
      }
      yaxis {
        min = "0"
        max = "100"
      }
    }
  }

  widget {
    timeseries_definition {
      title = "Memory Usage by Host"
      request {
        q = "avg:system.mem.used{*} by {host}"
        display_type = "area"
      }
    }
  }
}
```

### Application Performance Monitoring
```python
# app/monitoring.py
from datadog import initialize, statsd
from functools import wraps
import time

initialize(
    api_key='<DD_API_KEY>',
    app_key='<DD_APP_KEY>'
)

def monitor_performance(name, tags=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                statsd.increment(f'{name}.success', tags=tags)
                return result
            except Exception as e:
                statsd.increment(f'{name}.error', tags=tags + [f'error:{type(e).__name__}'])
                raise
            finally:
                duration = time.time() - start
                statsd.histogram(f'{name}.duration', duration, tags=tags)
        return wrapper
    return decorator

@monitor_performance('api.request', tags=['endpoint:users'])
def get_users():
    # API logic here
    pass

class CacheMonitoring:
    def __init__(self, cache_name):
        self.cache_name = cache_name

    def track_cache_hit(self, key):
        statsd.increment('cache.hit', tags=[f'cache:{self.cache_name}', f'key:{key}'])

    def track_cache_miss(self, key):
        statsd.increment('cache.miss', tags=[f'cache:{self.cache_name}', f'key:{key}'])

    def track_cache_size(self, size):
        statsd.gauge('cache.size', size, tags=[f'cache:{self.cache_name}'])
```

## Common Issues and Solutions

### Error: Agent Not Reporting
```error
Datadog Agent is not reporting metrics to Datadog
```

Solution:
1. Check agent status:
```bash
datadog-agent status
```

2. Verify API key:
```yaml
# /etc/datadog-agent/datadog.yaml
api_key: <YOUR_API_KEY>
site: datadoghq.com
```

3. Check network connectivity:
```bash
curl -X GET https://api.datadoghq.com/api/v1/validate \
-H "DD-API-KEY: ${DD_API_KEY}"
```

### Error: Missing Kubernetes Metrics
```error
No Kubernetes metrics appearing in Datadog
```

Solution:
1. Verify RBAC permissions:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: datadog-agent
rules:
  - apiGroups: [""]
    resources:
      - nodes
      - pods
      - services
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources:
      - nodes/metrics
      - nodes/spec
      - nodes/proxy
    verbs: ["get"]
```

2. Check kubelet configuration:
```yaml
kubelet:
  tlsVerify: false
  host: ${NODE_IP}
```

### Error: APM Not Working
```error
No traces appearing in Datadog APM
```

Solution:
1. Enable APM:
```yaml
apm_config:
  enabled: true
  env: production
```

2. Configure application:
```python
from ddtrace import config
config.env = 'production'
config.service = 'my-service'
config.version = '1.0.0'
```

3. Check port accessibility:
```bash
netstat -an | grep 8126
```
