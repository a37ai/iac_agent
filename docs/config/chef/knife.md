---
tool: chef
category: configuration_management
version: "17.0"
topics:
  - knife
  - cookbooks
  - recipes
---
# Chef Knife CLI Tool

## Common Operations

### Cookbook Management
```bash
# Create new cookbook
knife cookbook create mycookbook

# Upload cookbook
knife cookbook upload mycookbook

# List cookbooks
knife cookbook list
```

## Common Issues and Solutions

### Error: Authentication Failed
```error
ERROR: Failed to authenticate to the chef server
```

Solution:
1. Check knife configuration:
```bash
knife configure -i
```

2. Verify knife.rb:
```ruby
current_dir = File.dirname(__FILE__)
log_level                :info
log_location             STDOUT
node_name               "user"
client_key              "#{current_dir}/user.pem"
chef_server_url         "https://api.chef.io/organizations/org"
```

### Error: Cookbook Upload Failed
```error
ERROR: Cookbook upload failed due to checksum mismatch
```

Solution:
1. Clean chef cache:
```bash
rm -rf ~/.chef/cache/*
```

2. Verify cookbook version:
```ruby
# metadata.rb
name 'mycookbook'
version '0.1.0'
```

### Error: Node Not Found
```error
ERROR: The object you are looking for could not be found
```

Solution:
1. List nodes:
```bash
knife node list
```

2. Search nodes:
```bash
knife search node "role:webserver"
```

3. Bootstrap node:
```bash
knife bootstrap ADDRESS \
  --ssh-user USER \
  --sudo \
  --identity-file IDENTITY_FILE \
  --node-name node1 \
  --run-list 'recipe[mycookbook]'
```
