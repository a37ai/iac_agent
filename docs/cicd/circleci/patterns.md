---
tool: circleci
category: cicd
version: "2.1"
topics:
  - pipelines
  - orbs
  - workflows
  - testing
related_topics:
  - path: /cicd/github_actions/workflows.md
    description: "Comparing CircleCI and GitHub Actions"
  - path: /monitoring/datadog/integrations.md#circleci
    description: "Monitoring CircleCI pipelines"
  - path: /security/snyk/configuration.md#circleci
    description: "Security scanning in CircleCI"
  - path: /testing/cypress/configuration.md#circleci
    description: "E2E testing in CircleCI"
---

# CircleCI Pipeline Patterns

## Complex Multi-Tool Workflows

### Complete DevSecOps Pipeline
```yaml
# .circleci/config.yml
version: 2.1

orbs:
  docker: circleci/docker@2.4.0
  kubernetes: circleci/kubernetes@1.3.1
  snyk: snyk/snyk@1.4.0
  datadog: datadog/deploy@1.2.0

parameters:
  deploy-env:
    type: enum
    enum: [dev, staging, prod]
    default: dev

executors:
  node-docker:
    docker:
      - image: cimg/node:18.12
  python-docker:
    docker:
      - image: cimg/python:3.11

commands:
  setup-deployment:
    parameters:
      env:
        type: string
    steps:
      - kubernetes/install-kubectl
      - run:
          name: Setup Kubernetes Context
          command: |
            echo $KUBE_CONFIG_<< parameters.env >> | base64 -d > kubeconfig
            export KUBECONFIG=kubeconfig

jobs:
  test:
    executor: node-docker
    steps:
      - checkout
      - restore_cache:
          keys:
            - v1-deps-{{ checksum "package-lock.json" }}
      - run:
          name: Install Dependencies
          command: npm ci
      - save_cache:
          key: v1-deps-{{ checksum "package-lock.json" }}
          paths:
            - node_modules
      - run:
          name: Run Tests
          command: |
            npm run test:unit
            npm run test:integration
      - store_test_results:
          path: test-results
      - store_artifacts:
          path: coverage

  security-scan:
    executor: node-docker
    steps:
      - checkout
      - snyk/scan:
          severity-threshold: high
          monitor-on-build: true
          fail-on-issues: true
          additional-arguments: --all-projects

  build:
    executor: docker/docker
    steps:
      - checkout
      - setup_remote_docker:
          version: 20.10.14
          docker_layer_caching: true
      - docker/build:
          image: $DOCKER_IMAGE
          tag: $CIRCLE_SHA1
      - docker/push:
          image: $DOCKER_IMAGE
          tag: $CIRCLE_SHA1
      - run:
          name: Tag Latest
          command: |
            if [ "${CIRCLE_BRANCH}" = "main" ]; then
              docker tag $DOCKER_IMAGE:$CIRCLE_SHA1 $DOCKER_IMAGE:latest
              docker push $DOCKER_IMAGE:latest
            fi

  deploy:
    executor: kubernetes/default
    parameters:
      env:
        type: string
    steps:
      - checkout
      - setup-deployment:
          env: << parameters.env >>
      - kubernetes/create-or-update-resource:
          resource-file-path: k8s/deployment.yml
          resource-name: deployment/myapp
          show-kubectl-command: true
      - datadog/deploy-tracking:
          service: myapp
          env: << parameters.env >>

workflows:
  version: 2
  build-test-deploy:
    jobs:
      - test
      - security-scan:
          requires:
            - test
      - build:
          requires:
            - security-scan
      - deploy:
          name: deploy-dev
          env: dev
          requires:
            - build
          filters:
            branches:
              only: develop
      - approve-staging:
          type: approval
          requires:
            - deploy-dev
      - deploy:
          name: deploy-staging
          env: staging
          requires:
            - approve-staging
      - approve-prod:
          type: approval
          requires:
            - deploy-staging
      - deploy:
          name: deploy-prod
          env: prod
          requires:
            - approve-prod
          filters:
            branches:
              only: main

  nightly:
    triggers:
      - schedule:
          cron: "0 0 * * *"
          filters:
            branches:
              only:
                - main
    jobs:
      - security-scan
```

### Advanced Testing Matrix
```yaml
# .circleci/config.yml
version: 2.1

orbs:
  browser-tools: circleci/browser-tools@1.4.1

parameters:
  node-version:
    type: string
    default: "18.12"
  e2e-count:
    type: integer
    default: 4

executors:
  node-browser:
    parameters:
      node-version:
        type: string
    docker:
      - image: cimg/node:<< parameters.node-version >>-browsers

jobs:
  unit-test:
    parameters:
      node-version:
        type: string
    executor:
      name: node-browser
      node-version: << parameters.node-version >>
    steps:
      - checkout
      - restore_cache:
          keys:
            - v1-deps-{{ checksum "package-lock.json" }}
      - run:
          name: Install Dependencies
          command: npm ci
      - save_cache:
          key: v1-deps-{{ checksum "package-lock.json" }}
          paths:
            - node_modules
      - run:
          name: Run Unit Tests
          command: npm run test:unit
      - store_test_results:
          path: test-results/unit

  e2e-test:
    parameters:
      chunk:
        type: integer
      total:
        type: integer
    executor:
      name: node-browser
      node-version: << pipeline.parameters.node-version >>
    steps:
      - checkout
      - browser-tools/install-chrome
      - browser-tools/install-chromedriver
      - restore_cache:
          keys:
            - v1-deps-{{ checksum "package-lock.json" }}
      - run:
          name: Install Dependencies
          command: npm ci
      - run:
          name: Run E2E Tests
          command: |
            npx cypress run \
              --parallel \
              --record \
              --group "all tests" \
              --ci-build-id $CIRCLE_WORKFLOW_ID \
              --chunk << parameters.chunk >>/<< parameters.total >>
      - store_test_results:
          path: test-results/e2e
      - store_artifacts:
          path: cypress/videos
      - store_artifacts:
          path: cypress/screenshots

workflows:
  version: 2
  test-matrix:
    jobs:
      - unit-test:
          matrix:
            parameters:
              node-version: ["16.19", "18.12", "20.0"]
      - e2e-test:
          matrix:
            parameters:
              chunk: [1, 2, 3, 4]
              total: [<< pipeline.parameters.e2e-count >>]
          requires:
            - unit-test
```

## Integration Patterns

### Monorepo Build
```yaml
# .circleci/config.yml
version: 2.1

orbs:
  path-filtering: circleci/path-filtering@0.1.3

setup: true

jobs:
  generate-config:
    docker:
      - image: cimg/base:stable
    steps:
      - checkout
      - path-filtering/set-parameters:
          mapping: |
            frontend/.* run-frontend-tests true
            backend/.* run-backend-tests true
            shared/.* run-all-tests true
          base-revision: main
          output-path: pipeline-parameters.json
      - run:
          name: Generate Config
          command: |
            if [[ << pipeline.parameters.run-all-tests >> == true ]]; then
              echo 'export PARAM_FRONTEND=true' >> $BASH_ENV
              echo 'export PARAM_BACKEND=true' >> $BASH_ENV
            else
              echo 'export PARAM_FRONTEND=<< pipeline.parameters.run-frontend-tests >>' >> $BASH_ENV
              echo 'export PARAM_BACKEND=<< pipeline.parameters.run-backend-tests >>' >> $BASH_ENV
            fi
            source $BASH_ENV
            
            cat \<< EOF > generated_config.yml
            version: 2.1
            
            orbs:
              node: circleci/node@5.1.0
              python: circleci/python@2.1.1
            
            workflows:
              build-test:
                jobs:
                  - node/test:
                      name: frontend-test
                      app-dir: ~/project/frontend
                      run-command: test
                      version: "18.12"
                      filters:
                        branches:
                          ignore: main
                      when:
                        condition:
                          equal: [$PARAM_FRONTEND, true]
                  - python/test:
                      name: backend-test
                      app-dir: ~/project/backend
                      version: "3.11"
                      pkg-manager: pip
                      test-tool: pytest
                      filters:
                        branches:
                          ignore: main
                      when:
                        condition:
                          equal: [$PARAM_BACKEND, true]
            EOF
      - persist_to_workspace:
          root: .
          paths:
            - generated_config.yml

  continue:
    docker:
      - image: cimg/base:stable
    steps:
      - attach_workspace:
          at: .
      - continuation/continue:
          configuration_path: generated_config.yml

workflows:
  setup-workflow:
    jobs:
      - generate-config
      - continue:
          requires:
            - generate-config
```

### Multi-Region Deployment
```yaml
# .circleci/config.yml
version: 2.1

orbs:
  aws-cli: circleci/aws-cli@3.1.5
  kubernetes: circleci/kubernetes@1.3.1

parameters:
  regions:
    type: string
    default: "us-east-1,us-west-2,eu-west-1"

commands:
  deploy-region:
    parameters:
      region:
        type: string
    steps:
      - aws-cli/setup:
          region: << parameters.region >>
      - kubernetes/install-kubectl
      - run:
          name: Update Kubeconfig
          command: |
            aws eks update-kubeconfig \
              --name my-cluster \
              --region << parameters.region >>
      - kubernetes/create-or-update-resource:
          resource-file-path: k8s/deployment.yml
          resource-name: deployment/myapp
      - run:
          name: Verify Deployment
          command: |
            kubectl rollout status deployment/myapp \
              --timeout=300s

jobs:
  deploy:
    docker:
      - image: cimg/python:3.11
    parameters:
      region:
        type: string
    steps:
      - checkout
      - deploy-region:
          region: << parameters.region >>

workflows:
  deploy-all-regions:
    jobs:
      - deploy:
          matrix:
            parameters:
              region: 
                - us-east-1
                - us-west-2
                - eu-west-1
          filters:
            branches:
              only: main
```

## Common Issues and Solutions

### Error: Context Not Found
```error
Unable to find the context: my-context
```

Solution:
1. Check context exists:
```bash
circleci context list <organization-id>
```

2. Add context to workflow:
```yaml
workflows:
  build-deploy:
    jobs:
      - build:
          context: my-context
```

### Error: Resource Class Limits
```error
No available resource class matches the requested resource class
```

Solution:
1. Adjust resource class:
```yaml
jobs:
  build:
    docker:
      - image: cimg/node:18.12
    resource_class: medium
```

2. Request resource class approval:
```bash
circleci runner resource-class create <namespace>/<resource-class> --generate-token
```

### Error: Test Splitting
```error
Error: Unable to split tests, no timing data found
```

Solution:
1. Enable test splitting:
```yaml
jobs:
  test:
    parallelism: 4
    steps:
      - run:
          command: |
            TESTFILES=$(circleci tests glob "test/**/*.js" | circleci tests split --split-by=timings)
            npm test $TESTFILES
```

2. Store timing data:
```yaml
      - store_test_results:
          path: test-results
