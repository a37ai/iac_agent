---
tool: jenkins
category: cicd
version: "2.426"
topics:
  - pipelines
  - automation
  - security
  - testing
related_topics:
  - path: /containers/kubernetes/advanced_patterns.md#ci-cd
    description: "Kubernetes deployment with Jenkins"
  - path: /monitoring/prometheus/configuration.md#jenkins
    description: "Monitoring Jenkins pipelines"
  - path: /security/scanning/pipeline.md#jenkins
    description: "Security scanning in Jenkins"
  - path: /iac/terraform/jenkins_provider.md
    description: "Managing Jenkins with Terraform"
---

# Jenkins Pipeline Patterns

## Complex Multi-Tool Workflows

### Complete DevSecOps Pipeline
```groovy
// Jenkinsfile
def COLOR_MAP = [
    'SUCCESS': 'good',
    'FAILURE': 'danger',
    'UNSTABLE': 'warning'
]

pipeline {
    agent {
        kubernetes {
            yaml '''
                apiVersion: v1
                kind: Pod
                spec:
                  containers:
                  - name: maven
                    image: maven:3.8.4-openjdk-17
                    command:
                    - cat
                    tty: true
                  - name: docker
                    image: docker:20.10
                    command:
                    - cat
                    tty: true
                    volumeMounts:
                    - mountPath: /var/run/docker.sock
                      name: docker-sock
                  - name: trivy
                    image: aquasec/trivy:latest
                    command:
                    - cat
                    tty: true
                  volumes:
                  - name: docker-sock
                    hostPath:
                      path: /var/run/docker.sock
            '''
        }
    }

    environment {
        DOCKER_REGISTRY = 'registry.example.com'
        APP_NAME = 'myapp'
        SONAR_PROJECT_KEY = 'org.example:myapp'
        NEXUS_REPO = 'maven-releases'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 1, unit: 'HOURS')
        ansiColor('xterm')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Unit Tests') {
            steps {
                container('maven') {
                    sh '''
                        mvn clean test
                        mvn jacoco:report
                    '''
                }
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                    jacoco(
                        execPattern: '**/target/jacoco.exec',
                        classPattern: '**/target/classes',
                        sourcePattern: '**/src/main/java'
                    )
                }
            }
        }

        stage('Static Code Analysis') {
            parallel {
                stage('SonarQube Analysis') {
                    steps {
                        container('maven') {
                            withSonarQubeEnv('SonarQube') {
                                sh '''
                                    mvn sonar:sonar \
                                        -Dsonar.projectKey=$SONAR_PROJECT_KEY \
                                        -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml
                                '''
                            }
                        }
                        timeout(time: 10, unit: 'MINUTES') {
                            waitForQualityGate abortPipeline: true
                        }
                    }
                }

                stage('OWASP Dependency Check') {
                    steps {
                        container('maven') {
                            sh 'mvn org.owasp:dependency-check-maven:check'
                        }
                    }
                    post {
                        always {
                            dependencyCheckPublisher pattern: '**/dependency-check-report.xml'
                        }
                    }
                }
            }
        }

        stage('Build and Publish') {
            steps {
                container('maven') {
                    configFileProvider([configFile(fileId: 'maven-settings', variable: 'MAVEN_SETTINGS')]) {
                        sh '''
                            mvn -s $MAVEN_SETTINGS clean deploy \
                                -DskipTests \
                                -DaltDeploymentRepository=nexus::default::http://nexus:8081/repository/$NEXUS_REPO
                        '''
                    }
                }
            }
        }

        stage('Build Container') {
            steps {
                container('docker') {
                    script {
                        docker.withRegistry("https://${DOCKER_REGISTRY}", 'registry-credentials') {
                            def app = docker.build("${DOCKER_REGISTRY}/${APP_NAME}:${BUILD_NUMBER}")
                            app.push()
                            app.push('latest')
                        }
                    }
                }
            }
        }

        stage('Security Scan') {
            parallel {
                stage('Container Scan') {
                    steps {
                        container('trivy') {
                            sh """
                                trivy image --format json --output trivy-results.json \
                                    ${DOCKER_REGISTRY}/${APP_NAME}:${BUILD_NUMBER}
                            """
                        }
                    }
                    post {
                        always {
                            recordIssues(tools: [trivy(pattern: 'trivy-results.json')])
                        }
                    }
                }

                stage('DAST Scan') {
                    steps {
                        container('maven') {
                            sh 'mvn zap:analyze'
                        }
                    }
                    post {
                        always {
                            publishHTML(target: [
                                allowMissing: false,
                                alwaysLinkToLastBuild: true,
                                keepAll: true,
                                reportDir: 'target/zap-reports',
                                reportFiles: 'zap-report.html',
                                reportName: 'ZAP Security Report'
                            ])
                        }
                    }
                }
            }
        }

        stage('Deploy to Staging') {
            when {
                branch 'main'
            }
            steps {
                container('docker') {
                    withKubeConfig([credentialsId: 'kubeconfig']) {
                        sh '''
                            helm upgrade --install ${APP_NAME} ./helm \
                                --namespace staging \
                                --set image.repository=${DOCKER_REGISTRY}/${APP_NAME} \
                                --set image.tag=${BUILD_NUMBER}
                        '''
                    }
                }
            }
        }

        stage('Integration Tests') {
            when {
                branch 'main'
            }
            steps {
                container('maven') {
                    sh 'mvn verify -Pintegration-tests'
                }
            }
            post {
                always {
                    junit '**/target/failsafe-reports/*.xml'
                }
            }
        }

        stage('Performance Tests') {
            when {
                branch 'main'
            }
            steps {
                container('maven') {
                    sh 'mvn gatling:test'
                }
            }
            post {
                always {
                    gatlingArchive()
                }
            }
        }

        stage('Deploy to Production') {
            when {
                branch 'main'
            }
            steps {
                timeout(time: 1, unit: 'DAYS') {
                    input message: 'Deploy to production?'
                }
                container('docker') {
                    withKubeConfig([credentialsId: 'kubeconfig']) {
                        sh '''
                            helm upgrade --install ${APP_NAME} ./helm \
                                --namespace production \
                                --set image.repository=${DOCKER_REGISTRY}/${APP_NAME} \
                                --set image.tag=${BUILD_NUMBER}
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
            script {
                def buildStatus = currentBuild.result ?: 'SUCCESS'
                def color = COLOR_MAP[buildStatus]
                slackSend(
                    color: color,
                    message: """
                        *${buildStatus}:* Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'
                        *Duration:* ${currentBuild.durationString}
                        *Changes:* ${currentBuild.changeSets.size()}
                        More info at: ${env.BUILD_URL}
                    """.stripIndent()
                )
            }
        }
    }
}
```

## Integration Patterns

### Multi-Branch Pipeline with Feature Flags
```groovy
// Jenkinsfile
def BRANCH_CONFIG = [
    'main': [
        environment: 'production',
        features: ['all': false]
    ],
    'staging': [
        environment: 'staging',
        features: ['newFeature': true, 'betaFeature': true]
    ],
    'development': [
        environment: 'development',
        features: ['all': true]
    ]
]

pipeline {
    agent any

    environment {
        APP_ENV = BRANCH_CONFIG[BRANCH_NAME]?.environment ?: 'development'
        FEATURES = BRANCH_CONFIG[BRANCH_NAME]?.features ?: ['all': true]
    }

    stages {
        stage('Configure Environment') {
            steps {
                script {
                    def config = readJSON file: 'config.json'
                    config.environment = APP_ENV
                    config.features = FEATURES
                    writeJSON file: 'config.json', json: config
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    def deployScript = """
                        helm upgrade --install ${APP_NAME} ./helm \
                            --namespace ${APP_ENV} \
                            --set environment=${APP_ENV} \
                            --set features.newFeature=${FEATURES['newFeature']} \
                            --set features.betaFeature=${FEATURES['betaFeature']}
                    """
                    sh deployScript
                }
            }
        }
    }
}
```

### Blue-Green Deployment
```groovy
// Jenkinsfile
def getCurrentColor(namespace) {
    def services = sh(
        script: "kubectl get service -n ${namespace} -l app=${APP_NAME} -o jsonpath='{.items[0].metadata.labels.color}'",
        returnStdout: true
    ).trim()
    return services ?: 'blue'
}

def switchTraffic(namespace, newColor) {
    sh """
        kubectl patch service ${APP_NAME} -n ${namespace} -p '{"spec":{"selector":{"color":"${newColor}"}}}' 
    """
}

pipeline {
    agent any

    stages {
        stage('Deploy New Version') {
            steps {
                script {
                    def currentColor = getCurrentColor(NAMESPACE)
                    def newColor = currentColor == 'blue' ? 'green' : 'blue'

                    // Deploy new version
                    sh """
                        helm upgrade --install ${APP_NAME}-${newColor} ./helm \
                            --namespace ${NAMESPACE} \
                            --set color=${newColor} \
                            --set image.tag=${BUILD_NUMBER}
                    """

                    // Wait for deployment
                    sh """
                        kubectl rollout status deployment/${APP_NAME}-${newColor} -n ${NAMESPACE} --timeout=300s
                    """

                    // Switch traffic
                    switchTraffic(NAMESPACE, newColor)

                    // Wait for verification
                    timeout(time: 1, unit: 'HOURS') {
                        input message: "Verify new deployment. Continue?"
                    }

                    // Clean up old deployment
                    sh """
                        helm uninstall ${APP_NAME}-${currentColor} -n ${NAMESPACE}
                    """
                }
            }
        }
    }
}
```

## Common Issues and Solutions

### Error: Pipeline Timeout
```error
Pipeline timed out after 60 minutes
```

Solution:
1. Adjust timeout settings:
```groovy
options {
    timeout(time: 2, unit: 'HOURS')
}
```

2. Add checkpoint for long-running stages:
```groovy
stage('Long Running Task') {
    options {
        timeout(time: 30, unit: 'MINUTES')
    }
    steps {
        milestone()
        // Your steps here
    }
}
```

### Error: Resource Constraints
```error
No available executors on jenkins-agent
```

Solution:
1. Configure pod templates:
```groovy
podTemplate(
    containers: [
        containerTemplate(
            name: 'maven',
            image: 'maven:3.8.4',
            resourceRequestCpu: '500m',
            resourceLimitCpu: '1',
            resourceRequestMemory: '1Gi',
            resourceLimitMemory: '2Gi'
        )
    ]
) {
    node(POD_LABEL) {
        // Your steps here
    }
}
```

2. Add node labels:
```groovy
agent {
    label 'high-memory'
}
```

### Error: Credential Access
```error
ERROR: Unable to find credentials
```

Solution:
1. Use credential bindings:
```groovy
environment {
    DOCKER_CREDS = credentials('docker-registry')
    KUBE_CONFIG = credentials('kubeconfig')
}
```

2. Scope credentials properly:
```groovy
withCredentials([
    usernamePassword(
        credentialsId: 'nexus-creds',
        usernameVariable: 'NEXUS_USER',
        passwordVariable: 'NEXUS_PASS'
    )
]) {
    sh 'curl -u $NEXUS_USER:$NEXUS_PASS http://nexus:8081/...'
}
