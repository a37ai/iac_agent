# Import all functions from each module
from .artifact import (
    configure_llm,
    summarize_with_llm,
    fetch_nexus_data,
    summarize_nexus_data,
    fetch_artifactory_data,
    summarize_artifactory_data
)

from .cicd import (
    fetch_jenkins_data,
    summarize_jenkins_data,
    fetch_gitlab_data,
    summarize_gitlab_data,
    fetch_github_actions_data,
    summarize_github_actions_data,
    fetch_circleci_data,
    summarize_circleci_data
)

from .cm import (
    configure_llm,
    summarize_with_llm,
    fetch_ansible_data,
    summarize_ansible_data,
    fetch_chef_data,
    summarize_chef_data,
    fetch_puppet_data,
    summarize_puppet_data
)

from .cloud import (
    build_aws_session,
    fetch_aws_data,
    summarize_aws_data,
    fetch_azure_data,
    summarize_azure_data,
    fetch_gcp_data,
    summarize_gcp_data
)

from .orchestration import (
    fetch_k8s_data,
    summarize_k8s_data,
    fetch_swarm_data,
    summarize_swarm_data
)

from .observability import (
    fetch_prometheus_data,
    summarize_prometheus_data,
    fetch_grafana_data,
    summarize_grafana_data,
    fetch_elk_data,
    summarize_elk_data,
    fetch_datadog_data,
    summarize_datadog_data,
    summarize_splunk_data,
    summarize_newrelic_data
)

from .networking import (
    fetch_istio_data,
    summarize_istio_data,
    fetch_consul_data,
    summarize_consul_data
)

from .container import (
    fetch_docker_data,
    summarize_docker_data,
    fetch_podman_data,
    summarize_podman_data
)

# Define what should be exposed with "from context_tools import *"
__all__ = [
    # Utility functions
    # 'configure_llm',
    # 'summarize_with_llm',
    
    # Artifact functions
    'fetch_nexus_data',
    'summarize_nexus_data',
    'fetch_artifactory_data',
    'summarize_artifactory_data',
    
    # CI/CD functions
    'fetch_jenkins_data',
    'summarize_jenkins_data',
    'fetch_gitlab_data',
    'summarize_gitlab_data',
    'fetch_github_actions_data',
    'summarize_github_actions_data',
    'fetch_circleci_data',
    'summarize_circleci_data',
    
    # Configuration Management functions
    'fetch_ansible_data',
    'summarize_ansible_data',
    'fetch_chef_data',
    'summarize_chef_data',
    'fetch_puppet_data',
    'summarize_puppet_data',
    
    # Cloud functions
    'build_aws_session',
    'fetch_aws_data',
    'summarize_aws_data',
    'fetch_azure_data',
    'summarize_azure_data',
    'fetch_gcp_data',
    'summarize_gcp_data',

    # Orchestration functions
    'fetch_k8s_data',
    'summarize_k8s_data',
    'fetch_swarm_data',
    'summarize_swarm_data',
    
    # Observability functions
    'fetch_prometheus_data',
    'summarize_prometheus_data',
    'fetch_grafana_data',
    'summarize_grafana_data',
    'fetch_elk_data',
    'summarize_elk_data',
    'fetch_datadog_data',
    'summarize_datadog_data',
    'summarize_splunk_data',
    'summarize_newrelic_data',
    
    # Networking functions
    'fetch_istio_data',
    'summarize_istio_data',
    'fetch_consul_data',
    'summarize_consul_data',
    
    # Container functions
    'fetch_docker_data',
    'summarize_docker_data',
    'fetch_podman_data',
    'summarize_podman_data'
]
