---
tool: gitlab
category: cicd
version: "16.0"
topics:
  - pipelines
  - runners
  - ci/cd
---
# GitLab CI/CD Configuration

## Common Patterns

### Basic Pipeline
```yaml
stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - docker build -t myapp .
  tags:
    - docker

test:
  stage: test
  script:
    - docker run myapp npm test
  tags:
    - docker
```

## Common Issues and Solutions

### Error: Runner Not Found
```error
This job is stuck because you don't have any active runners
```

Solution:
1. Check runner status:
```bash
gitlab-runner verify
```

2. Register new runner:
```bash
gitlab-runner register \
  --url "https://gitlab.com/" \
  --registration-token "PROJECT_REGISTRATION_TOKEN" \
  --description "docker-runner" \
  --executor "docker" \
  --docker-image alpine:latest
```

### Error: Pipeline Cache Failed
```error
Uploading artifacts to coordinator... forbidden
```

Solution:
1. Configure cache:
```yaml
cache:
  key: ${CI_COMMIT_REF_SLUG}
  paths:
    - node_modules/
  policy: pull-push
```

2. Check storage quota:
```bash
gitlab-ctl status
```

### Error: Docker Build Failed
```error
ERROR: error during connect: Get http://docker:2375: dial tcp: lookup docker on X.X.X.X:53: no such host
```

Solution:
1. Configure Docker service:
```yaml
services:
  - docker:dind

variables:
  DOCKER_HOST: tcp://docker:2375
  DOCKER_TLS_CERTDIR: ""
```

2. Use Docker-in-Docker:
```yaml
image: docker:latest

services:
  - name: docker:dind
    command: ["--tls=false"]
```
