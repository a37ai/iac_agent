---
tool: elk_stack
category: monitoring
version: "8.0"
topics:
  - elasticsearch
  - logstash
  - kibana
---
# ELK Stack Configuration

## Common Operations

### Elasticsearch Configuration
```yaml
# elasticsearch.yml
cluster.name: my-cluster
node.name: node-1
network.host: 0.0.0.0
discovery.seed_hosts: ["host1", "host2"]
cluster.initial_master_nodes: ["node-1"]
```

### Logstash Pipeline
```ruby
input {
  beats {
    port => 5044
  }
}

filter {
  grok {
    match => { "message" => "%{COMBINEDAPACHELOG}" }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "logstash-%{+YYYY.MM.dd}"
  }
}
```

## Common Issues and Solutions

### Error: Elasticsearch Cluster Health
```error
RED (cluster health status)
```

Solution:
1. Check cluster status:
```bash
curl -X GET "localhost:9200/_cluster/health?pretty"
```

2. Fix split brain:
```yaml
# elasticsearch.yml
discovery.zen.minimum_master_nodes: 2
```

### Error: Logstash Pipeline Failed
```error
Pipeline aborted due to error
```

Solution:
1. Test config:
```bash
logstash -f pipeline.conf --config.test_and_exit
```

2. Debug pipeline:
```bash
logstash -f pipeline.conf --debug
```

### Error: Kibana Cannot Connect
```error
Unable to connect to Elasticsearch at http://localhost:9200
```

Solution:
1. Check Elasticsearch:
```bash
curl localhost:9200
```

2. Configure Kibana:
```yaml
# kibana.yml
elasticsearch.hosts: ["http://localhost:9200"]
elasticsearch.username: "kibana_system"
elasticsearch.password: "password"
```

3. Set up security:
```bash
elasticsearch-setup-passwords interactive
```
