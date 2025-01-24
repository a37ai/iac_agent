---
tool: circleci
category: cicd
version: "2.1"
topics:
  - pipelines
  - orbs
  - workflows
---
# CircleCI Configuration

## Common Patterns

### Basic Config
```yaml
version: 2.1
orbs:
  node: circleci/node@4.7
jobs:
  build:
    docker:
      - image: cimg/node:16.10
    steps:
      - checkout
      - node/install-packages
      - run: npm test
```

## Common Issues and Solutions

### Error: No Config Found
```error
Error: No CircleCI configuration file was found in your repository
```

Solution:
1. Create config file:
```bash
mkdir -p .circleci
touch .circleci/config.yml
```

2. Validate config:
```bash
circleci config validate
```

### Error: Resource Class Not Found
```error
Error: resource_class 'xyz' not found
```

Solution:
1. Use valid resource class:
```yaml
jobs:
  build:
    docker:
      - image: cimg/node:16.10
    resource_class: medium
```

2. Check project settings:
```bash
circleci project settings
```

### Error: Context Not Found
```error
Error: Context 'xyz' not found
```

Solution:
1. Create context:
```bash
circleci context create github org-name context-name
```

2. Use context:
```yaml
workflows:
  build-test:
    jobs:
      - build:
          context: my-context
```

3. Add environment variables:
```bash
circleci context store-secret github org-name \
  context-name MY_SECRET_VAR
```
