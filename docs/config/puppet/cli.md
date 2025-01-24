---
tool: puppet
category: configuration_management
version: "7.0"
topics:
  - manifests
  - modules
  - agents
---
# Puppet CLI Tools

## Common Operations

### Module Management
```bash
# Create new module
puppet module generate author-mymodule

# Install module
puppet module install puppetlabs-apache

# List modules
puppet module list
```

## Common Issues and Solutions

### Error: Certificate Verification Failed
```error
Error: SSL_connect returned=1 errno=0 state=error: certificate verify failed
```

Solution:
1. Clean SSL:
```bash
puppet ssl clean
```

2. Generate new certificate:
```bash
puppet ssl bootstrap
```

3. Sign certificate on master:
```bash
puppetserver ca sign --certname agent.example.com
```

### Error: Catalog Compilation Failed
```error
Error: Could not retrieve catalog; skipping run
```

Solution:
1. Check manifest syntax:
```bash
puppet parser validate init.pp
```

2. Test compilation:
```bash
puppet apply --noop manifest.pp
```

3. Debug catalog:
```bash
puppet catalog compile --debug
```

### Error: Resource Dependencies
```error
Error: Found 1 dependency cycle
```

Solution:
1. Check resource ordering:
```puppet
package { 'nginx':
  ensure => installed,
  before => Service['nginx'],
}

service { 'nginx':
  ensure  => running,
  require => Package['nginx'],
}
```

2. Use relationships:
```puppet
Package['nginx'] -> Service['nginx']
```
