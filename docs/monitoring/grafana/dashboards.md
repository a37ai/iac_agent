---
tool: grafana
category: monitoring
version: "10.0"
topics:
  - dashboards
  - alerts
  - visualization
  - metrics
related_topics:
  - path: /monitoring/prometheus/configuration.md#data-sources
    description: "Configuring Prometheus as data source"
  - path: /monitoring/datadog/agent.md#grafana-integration
    description: "Integrating Datadog with Grafana"
  - path: /monitoring/elk/setup.md#grafana-kibana
    description: "Using ELK Stack with Grafana"
  - path: /containers/kubernetes/advanced_patterns.md#monitoring
    description: "Kubernetes monitoring patterns"
  - path: /cicd/github_actions/workflows.md#monitoring
    description: "CI/CD pipeline monitoring"
---
# Grafana Dashboards and Monitoring

## Complex Multi-Tool Workflows

### Complete Kubernetes Monitoring Stack
```yaml
# prometheus-operator-values.yaml
prometheus:
  prometheusSpec:
    retention: 15d
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: standard
          resources:
            requests:
              storage: 50Gi
    additionalScrapeConfigs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true

grafana:
  dashboardProviders:
    dashboardproviders.yaml:
      apiVersion: 1
      providers:
        - name: 'default'
          orgId: 1
          folder: ''
          type: file
          disableDeletion: false
          editable: true
          options:
            path: /var/lib/grafana/dashboards

  dashboards:
    default:
      kubernetes-cluster:
        file: dashboards/kubernetes-cluster.json
      node-exporter:
        file: dashboards/node-exporter.json
      application:
        file: dashboards/application.json

  datasources:
    datasources.yaml:
      apiVersion: 1
      datasources:
        - name: Prometheus
          type: prometheus
          url: http://prometheus-server
          access: proxy
          isDefault: true
        - name: Elasticsearch
          type: elasticsearch
          url: http://elasticsearch:9200
          access: proxy
          database: "[logstash-]YYYY.MM.DD"
```

### Advanced Dashboard with Multiple Data Sources
```json
{
  "dashboard": {
    "id": null,
    "title": "Application Performance Dashboard",
    "tags": ["kubernetes", "application"],
    "timezone": "browser",
    "schemaVersion": 21,
    "version": 0,
    "refresh": "5s",
    "panels": [
      {
        "title": "Pod CPU Usage",
        "type": "graph",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "sum(rate(container_cpu_usage_seconds_total{pod=~\"$pod\"}[5m])) by (pod)",
            "legendFormat": "{{pod}}"
          }
        ]
      },
      {
        "title": "Error Logs",
        "type": "logs",
        "datasource": "Elasticsearch",
        "targets": [
          {
            "query": "kubernetes.pod_name:$pod AND level:error",
            "metrics": [
              {
                "type": "count",
                "id": "1"
              }
            ]
          }
        ]
      },
      {
        "title": "API Response Time",
        "type": "heatmap",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "rate(http_request_duration_seconds_bucket{service=\"$service\"}[5m])",
            "format": "heatmap"
          }
        ]
      }
    ],
    "templating": {
      "list": [
        {
          "name": "pod",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(kube_pod_info, pod)"
        },
        {
          "name": "service",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(kube_service_info, service)"
        }
      ]
    }
  }
}
```

### Alert Configuration with Multiple Channels
```yaml
apiVersion: 1
groups:
  - name: kubernetes
    folder: Kubernetes
    interval: 1m
    rules:
      - name: High Pod Memory Usage
        condition: B
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'container_memory_usage_bytes{container!=""} / container_spec_memory_limit_bytes{container!=""} * 100 > 90'
          - refId: B
            datasourceUid: prometheus
            model:
              expr: 'count(container_memory_usage_bytes{container!=""} / container_spec_memory_limit_bytes{container!=""} * 100 > 90) > 0'
        noDataState: OK
        execErrState: Error
        for: 5m
        notifications:
          - uid: slack-notifications
          - uid: pagerduty-critical

  - name: application
    folder: Application
    interval: 30s
    rules:
      - name: High Error Rate
        condition: C
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)'
          - refId: B
            datasourceUid: prometheus
            model:
              expr: 'sum(rate(http_requests_total[5m])) by (service)'
          - refId: C
            expression: '$A / $B * 100 > 5'
        noDataState: OK
        execErrState: Error
        for: 2m
        notifications:
          - uid: slack-notifications
```

## Common Integration Patterns

### Kubernetes Resource Monitoring
```json
{
  "dashboard": {
    "title": "Kubernetes Resource Dashboard",
    "panels": [
      {
        "title": "Node Status",
        "type": "gauge",
        "targets": [
          {
            "expr": "sum(kube_node_status_condition{condition=\"Ready\",status=\"true\"}) / sum(kube_node_status_condition{condition=\"Ready\"})",
            "format": "time_series"
          }
        ],
        "options": {
          "reduceOptions": {
            "values": false,
            "calcs": ["lastNotNull"],
            "fields": ""
          },
          "orientation": "horizontal",
          "showThresholdLabels": false,
          "showThresholdMarkers": true
        }
      }
    ]
  }
}
```

### Application Performance Monitoring
```json
{
  "dashboard": {
    "title": "Application Performance",
    "panels": [
      {
        "title": "Request Latency",
        "type": "timeseries",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "p95"
          },
          {
            "expr": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
            "legendFormat": "p99"
          }
        ]
      }
    ]
  }
}
