---
tool: elk_stack
category: monitoring
version: "8.12"
topics:
  - logging
  - metrics
  - apm
  - security
related_topics:
  - path: /monitoring/prometheus/configuration.md#metrics
    description: "Integrating Prometheus metrics"
  - path: /monitoring/grafana/dashboards.md#elasticsearch
    description: "Using Elasticsearch as Grafana data source"
  - path: /containers/kubernetes/advanced_patterns.md#logging
    description: "Kubernetes logging with ELK"
  - path: /security/logging/audit.md#elk
    description: "Security audit logging with ELK"
---

# ELK Stack Integration Patterns

## Complex Multi-Tool Workflows

### Complete Observability Stack
```yaml
# docker-compose.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    environment:
      - node.name=es01
      - cluster.name=es-docker-cluster
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=true
      - xpack.security.enrollment.enabled=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - elastic

  logstash:
    image: docker.elastic.co/logstash/logstash:8.12.0
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline:ro
      - ./logstash/config/logstash.yml:/usr/share/logstash/config/logstash.yml:ro
    ports:
      - "5044:5044"
      - "5000:5000/tcp"
      - "5000:5000/udp"
      - "9600:9600"
    environment:
      LS_JAVA_OPTS: "-Xmx256m -Xms256m"
    networks:
      - elastic
    depends_on:
      - elasticsearch

  kibana:
    image: docker.elastic.co/kibana/kibana:8.12.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    networks:
      - elastic
    depends_on:
      - elasticsearch

  apm-server:
    image: docker.elastic.co/apm/apm-server:8.12.0
    ports:
      - "8200:8200"
    environment:
      - output.elasticsearch.hosts=["elasticsearch:9200"]
    networks:
      - elastic
    depends_on:
      - elasticsearch
      - kibana

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.12.0
    user: root
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - elastic
    depends_on:
      - elasticsearch
      - logstash

networks:
  elastic:
    driver: bridge

volumes:
  es-data:
    driver: local
```

### Advanced Log Processing
```ruby
# logstash/pipeline/main.conf
input {
  beats {
    port => 5044
  }
  tcp {
    port => 5000
    codec => json
  }
  http {
    port => 8080
    codec => json
  }
}

filter {
  if [container][labels][app] == "web" {
    grok {
      match => { "message" => "%{COMBINEDAPACHELOG}" }
    }
    date {
      match => [ "timestamp", "dd/MMM/yyyy:HH:mm:ss Z" ]
      target => "@timestamp"
    }
    geoip {
      source => "clientip"
    }
  }

  if [kubernetes][namespace] {
    mutate {
      add_field => {
        "env" => "%{[kubernetes][namespace]}"
        "pod_name" => "%{[kubernetes][pod][name]}"
      }
    }
    if [kubernetes][labels][version] {
      mutate {
        add_field => { "version" => "%{[kubernetes][labels][version]}" }
      }
    }
  }

  if [level] == "error" {
    mutate {
      add_tag => ["error"]
      add_field => { "priority" => "high" }
    }
    throttle {
      before_count => 3
      after_count => 5
      period => 3600
      key => "%{message}"
      add_tag => "throttled"
    }
  }
}

output {
  if "error" in [tags] {
    elasticsearch {
      hosts => ["elasticsearch:9200"]
      index => "errors-%{+YYYY.MM.dd}"
      user => "${ELASTIC_USER}"
      password => "${ELASTIC_PASSWORD}"
    }
    http {
      url => "http://alert-service:8080/api/alerts"
      format => "json"
      http_method => "post"
    }
  } else {
    elasticsearch {
      hosts => ["elasticsearch:9200"]
      index => "logs-%{[kubernetes][namespace]}-%{+YYYY.MM}"
      user => "${ELASTIC_USER}"
      password => "${ELASTIC_PASSWORD}"
    }
  }
}
```

### APM Integration
```yaml
# apm-server.yml
apm-server:
  host: "0.0.0.0:8200"
  rum:
    enabled: true
    rate_limit: 10
    source_mapping:
      enabled: true
      elasticsearch:
        indices:
          - "apm-source-map*"

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  username: "${ELASTIC_USER}"
  password: "${ELASTIC_PASSWORD}"
  indices:
    - index: "apm-%{[service.name]}-metric-%{+yyyy.MM.dd}"
      when.contains:
        processor.event: metric
    - index: "apm-%{[service.name]}-error-%{+yyyy.MM.dd}"
      when.contains:
        processor.event: error
    - index: "apm-%{[service.name]}-transaction-%{+yyyy.MM.dd}"
      when.contains:
        processor.event: transaction

setup.template.enabled: true
setup.template.name: "apm-%{[observer.version]}"
setup.template.pattern: "apm-*"
setup.kibana:
  host: "kibana:5601"
```

## Integration Patterns

### Kubernetes Logging
```yaml
# filebeat-kubernetes.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: filebeat-config
  namespace: logging
data:
  filebeat.yml: |-
    filebeat.inputs:
    - type: container
      paths:
        - /var/log/containers/*.log
      processors:
        - add_kubernetes_metadata:
            host: ${NODE_NAME}
            matchers:
            - logs_path:
                logs_path: "/var/log/containers/"

    output.elasticsearch:
      hosts: ['${ELASTICSEARCH_HOST:elasticsearch}:${ELASTICSEARCH_PORT:9200}']
      username: ${ELASTICSEARCH_USERNAME}
      password: ${ELASTICSEARCH_PASSWORD}

    setup.ilm.enabled: true
    setup.ilm.rollover_alias: "kubernetes-%{[agent.version]}"
    setup.template.name: "kubernetes-%{[agent.version]}"
    setup.template.pattern: "kubernetes-%{[agent.version]}-*"

---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: filebeat
  namespace: logging
spec:
  selector:
    matchLabels:
      app: filebeat
  template:
    metadata:
      labels:
        app: filebeat
    spec:
      serviceAccountName: filebeat
      terminationGracePeriodSeconds: 30
      containers:
      - name: filebeat
        image: docker.elastic.co/beats/filebeat:8.12.0
        args: [
          "-c", "/etc/filebeat.yml",
          "-e",
        ]
        env:
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        securityContext:
          runAsUser: 0
        resources:
          limits:
            memory: 200Mi
          requests:
            cpu: 100m
            memory: 100Mi
        volumeMounts:
        - name: config
          mountPath: /etc/filebeat.yml
          readOnly: true
          subPath: filebeat.yml
        - name: data
          mountPath: /usr/share/filebeat/data
        - name: varlibdockercontainers
          mountPath: /var/lib/docker/containers
          readOnly: true
        - name: varlog
          mountPath: /var/log
          readOnly: true
      volumes:
      - name: config
        configMap:
          defaultMode: 0600
          name: filebeat-config
      - name: data
        hostPath:
          path: /var/lib/filebeat-data
          type: DirectoryOrCreate
      - name: varlibdockercontainers
        hostPath:
          path: /var/lib/docker/containers
      - name: varlog
        hostPath:
          path: /var/log
```

### Metrics Collection
```yaml
# metricbeat.yml
metricbeat.modules:
- module: system
  metricsets:
    - cpu
    - load
    - memory
    - network
    - process
  enabled: true
  period: 10s
  processes: ['.*']

- module: docker
  metricsets:
    - container
    - cpu
    - diskio
    - healthcheck
    - info
    - memory
    - network
  hosts: ["unix:///var/run/docker.sock"]
  period: 10s

- module: kubernetes
  metricsets:
    - container
    - node
    - pod
    - system
    - volume
  period: 10s
  hosts: ["https://${NODE_NAME}:10250"]
  bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
  ssl.verification_mode: "none"

output.elasticsearch:
  hosts: ['${ELASTICSEARCH_HOST:elasticsearch}:${ELASTICSEARCH_PORT:9200}']
  username: ${ELASTICSEARCH_USERNAME}
  password: ${ELASTICSEARCH_PASSWORD}
```

## Common Issues and Solutions

### Error: Elasticsearch Out of Memory
```error
java.lang.OutOfMemoryError: Java heap space
```

Solution:
1. Adjust JVM heap size:
```yaml
environment:
  - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
```

2. Enable index lifecycle management:
```json
PUT _ilm/policy/logs-policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "7d"
          }
        }
      },
      "warm": {
        "min_age": "30d",
        "actions": {
          "shrink": {
            "number_of_shards": 1
          },
          "forcemerge": {
            "max_num_segments": 1
          }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

### Error: Logstash Pipeline Delays
```error
Pipeline has fallen behind real-time processing
```

Solution:
1. Optimize pipeline configuration:
```ruby
input {
  beats {
    port => 5044
    client_inactivity_timeout => 60
    batch_size => 2048
  }
}

filter {
  mutate {
    remove_field => [ "tags", "beat", "input_type", "offset", "source", "type" ]
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    manage_template => false
    template_overwrite => false
    worker_pool_size => 2
    bulk_size => 1000
    flush_size => 500
  }
}
```

2. Enable persistent queues:
```yaml
queue.type: persisted
queue.max_bytes: 4gb
```

### Error: APM Data Missing
```error
No APM data appearing in Kibana
```

Solution:
1. Check APM agent configuration:
```python
# Python example
from elasticapm.contrib.flask import ElasticAPM

app.config['ELASTIC_APM'] = {
    'SERVICE_NAME': 'my-service',
    'SERVER_URL': 'http://apm-server:8200',
    'ENVIRONMENT': 'production',
    'CAPTURE_BODY': 'all'
}
ElasticAPM(app)
