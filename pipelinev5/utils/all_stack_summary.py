import os
from supabase import create_client, Client
import traceback
from termcolor import colored

class Supabase:
    def __init__(self, access_token: str = None, refresh_token: str = None, user_auth=False):
        url: str = os.getenv("SUPABASE_URL", "")
        key: str = os.getenv("SUPABASE_KEY", "")
        
        if not url or not key:
            raise ValueError("Supabase URL or Key is not set in the environment variables.")

        try:    
            self.supabase: Client = create_client(url, key)
            if user_auth:
                # Optionally set session details if required
                self.supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
                pass
        except Exception as e:
            traceback.print_exc()
            raise ValueError(f"Failed to initialize Supabase client: {str(e)}")
        
    def get_project_data(self, project_id: str):
        response = self.supabase.table("projects").select("*").eq("id", project_id).execute()
        data = response.data
        if not data:
            raise ValueError(f"No project data found for project {project_id}")
        if type(data) is list:
            return data[0]
        elif type(data) is dict:
            return data
        else:
            raise ValueError(f"Unexpected data type: {type(data)}")

    def set_aws_credentials(access_token: str = "", refresh_token: str = "", project_id: str = ""):
        # Retrieve variables from .env
        url: str = os.getenv("SUPABASE_URL") 
        key: str = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("Supabase URL or Key is not set in the environment variables.")

        try:
            supabase: Client = create_client(url, key)
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            
            # Execute the query
            response = supabase.table("projects").select("aws_access_key_id, aws_secret_access_key").eq("id", project_id).execute()
            
            if not response.data:
                raise ValueError(f"No AWS credentials found for project {project_id}")
                
            return response
            
        except Exception as e:
            raise ValueError(f"Failed to retrieve AWS credentials: {str(e)}")

    def update_project_data(self, project_id: str, codebase_understanding: dict) -> None:
        """Update project's codebase understanding in Supabase."""
        try:
            self.supabase.table("projects").update({
                "codebase_understanding": codebase_understanding
            }).eq("id", project_id).execute()
        except Exception as e:
            raise ValueError(f"Failed to update project data: {str(e)}")

    def get_integration_raw_data(self, integration_name: str, project_id: str):
        """
        Get raw data for a specific integration from the projects table.
        
        Args:
            integration_name: Name of the integration tool
            project_id: ID of the project
            
        Returns:
            Response object containing the data
            
        Raises:
            ValueError: If the query fails or returns invalid data
        """
        if not project_id or project_id == "None":
            raise ValueError("A valid project_id must be provided")
        try:
            integration_column = f"{integration_name}_raw"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            
            if not response:
                print(f"Failed to retrieve {integration_name} data")
                return None
                
            return str(response.data)
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")
    
    def get_integration_summarized_data(self, integration_name: str, project_id: str):
        """
        Get summarized data for a specific integration from the projects table.
        
        Args:
            integration_name: Name of the integration tool
            project_id: ID of the project
            
        Returns:
            Response object containing the data
            
        Raises:
            ValueError: If the query fails or returns invalid data
        """
        if not project_id or project_id == "None":
            raise ValueError("A valid project_id must be provided")
        colored(f"Retrieving {project_id}'s {integration_name} summary", "green")
        colored(f"Retrieving {project_id}'s {integration_name} summary", "green")
        try:
            integration_column = f"{integration_name}_summary"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            
            if not response.data[0][integration_column]:
                print(f"No {integration_name} summary")
                return None
            
            return str(response.data[0][integration_column])
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")


artifactory_tools = ["artifactory", "nexus"]
cicd_tools = ["jenkins", "github", "gitlab", "circleci"]
cloud_tools = ["aws", "azure", "gcp"]
cm_tools = ["ansible", "chef", "puppet"]
container_tools = ["docker", "podman"]
networking_tools = ["istio", "consul"]
observability_tools = ["datadog", "new_relic", "splunk", "elasticsearch", "grafana", "prometheus"]
orchestration_tools = ["kubernetes", "docker_swarm"]

all_tools = artifactory_tools + cicd_tools + cloud_tools + cm_tools + container_tools + networking_tools + observability_tools + orchestration_tools
def all_stack_summary(project_id: str):
    supabase = Supabase()
    full_summary = ""
    
    for tool in all_tools:
        tool_summary = supabase.get_integration_summarized_data(tool, project_id)
        if tool_summary:
            full_summary += tool_summary

    return full_summary    

def get_configured_integrations(project_id: str):
    """
    Given a project ID, return a list of integrations that have been configured
    for that project in Supabase. We check each potential integration's credentials 
    in the 'projects' table. If those fields are populated, we consider that integration 'enabled'.
    """
    supabase_client = Supabase()
    response = supabase_client.supabase.table("projects").select("*").eq("id", project_id).execute()

    if not response.data:
        print(f"No project found with id={project_id}")
        return []

    # There should be exactly one matching row if `id` is unique.
    project = response.data[0]

    configured_integrations = []

    # -----------------------------------------
    # Example checks for each integration below
    # -----------------------------------------

    # Jenkins
    if project.get("jenkins_url") and project.get("jenkins_user") and project.get("jenkins_api_token"):
        configured_integrations.append("jenkins")

    # GitLab
    if project.get("gitlab_url") and project.get("gitlab_token"):
        configured_integrations.append("gitlab")

    # GitHub Actions
    if project.get("github_url") and project.get("github_token") and project.get("github_owner") and project.get("github_repo"):
        configured_integrations.append("github_actions")

    # CircleCI
    if project.get("circleci_api_url") and project.get("circleci_personal_token") and project.get("circleci_project_slug"):
        configured_integrations.append("circleci")

    # AWS
    if project.get("aws_access_key_id") and project.get("aws_secret_access_key") and project.get("aws_default_region"):
        configured_integrations.append("aws")

    # Azure
    if (project.get("azure_tenant_id") and project.get("azure_client_id") 
        and project.get("azure_client_secret") and project.get("azure_subscription_id")):
        configured_integrations.append("azure")

    # GCP
    if project.get("gcp_service_account_json_content") and project.get("gcp_project_id"):
        configured_integrations.append("gcp")

    # Kubernetes
    kube_config_content = project.get("kube_config_file_content")
    kube_config_name = project.get("kube_config_file_name")
    kube_service_account_token = project.get("kube_service_account_token")
    kube_host = project.get("kube_host")
    if (kube_config_content and kube_config_name) or (kube_service_account_token and kube_host):
        configured_integrations.append("kubernetes")

    # Docker Swarm (example check, you might have different fields)
    if (project.get("docker_username") and project.get("docker_password")) \
       or (project.get("docker_config_file_content") and project.get("docker_config_file_name")):
        configured_integrations.append("docker_swarm")

    # Docker
    docker_username = project.get("docker_username")
    docker_password = project.get("docker_password")
    docker_config_content = project.get("docker_config_file_content")
    docker_config_name = project.get("docker_config_file_name")
    if (docker_username and docker_password) or (docker_config_content and docker_config_name):
        configured_integrations.append("docker")

    # Podman
    if project.get("podman_url"):
        configured_integrations.append("podman")

    # Prometheus
    if project.get("prometheus_url"):
        configured_integrations.append("prometheus")

    # Grafana
    if project.get("grafana_url") and project.get("grafana_api_key"):
        configured_integrations.append("grafana")

    # ELK
    if (project.get("elasticsearch_url") and project.get("elasticsearch_username") and project.get("elasticsearch_password")) \
       or (project.get("logstash_url") and project.get("logstash_username") and project.get("logstash_password")) \
       or (project.get("kibana_url") and project.get("kibana_username") and project.get("kibana_password")):
        configured_integrations.append("elk")

    # Datadog
    if project.get("datadog_api_key") and project.get("datadog_app_key"):
        configured_integrations.append("datadog")

    # New Relic
    if project.get("new_relic_api_key") and project.get("new_relic_account_id"):
        configured_integrations.append("newrelic")

    # Splunk
    if project.get("splunk_url") and project.get("splunk_username") and project.get("splunk_password"):
        configured_integrations.append("splunk")

    # Istio
    istio_kubeconfig_content = project.get("istio_kubeconfig_file_content")
    istio_kubeconfig_name = project.get("istio_kubeconfig_file_name")
    istio_host = project.get("istio_host")
    istio_bearer_token = project.get("istio_bearer_token")
    if (istio_kubeconfig_content and istio_kubeconfig_name) or (istio_host and istio_bearer_token):
        configured_integrations.append("istio")

    # Consul
    if project.get("consul_url") and project.get("consul_token"):
        configured_integrations.append("consul")

    # Puppet
    if project.get("puppet_host_url") and project.get("puppet_token"):
        configured_integrations.append("puppet")

    # Chef
    if (project.get("chef_server_url") and project.get("chef_client_name") 
        and project.get("chef_pem_file_content") and project.get("chef_pem_file_name")):
        configured_integrations.append("chef")

    # Ansible
    if project.get("ansible_tower_url") and project.get("ansible_tower_token"):
        configured_integrations.append("ansible")

    # Artifactory
    if project.get("artifactory_url") and project.get("artifactory_username") and project.get("artifactory_password"):
        configured_integrations.append("artifactory")

    # Nexus
    if project.get("nexus_url") and project.get("nexus_username") and project.get("nexus_password"):
        configured_integrations.append("nexus")

    # Return the list of configured integrations
    return configured_integrations


# print(get_configured_integrations("89f1b2c5-c78b-426e-9567-62c8cac1c61e"))

# supabase_client = Supabase()
# all_projects = supabase_client.supabase.table("projects").select("*").execute()
# print("All projects table data:", all_projects.data)