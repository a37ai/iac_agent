import json
import requests
import chef
import google.generativeai as genai
from typing import Dict, Any

import os

"""
Context Generation Tools For Configuration Management (CM) Tools

"""

def configure_llm(api_key: str):

    """
    Configure the Google Generative AI client to use the specified API key.
    """
    genai.configure(api_key=api_key)

def summarize_with_llm(
    model_name: str,
    raw_data: str,
    prompt_instructions: str
) -> str:
    """
    Send raw data and instructions to the specified Gemini model, returning a summary.

    :param model_name: The Gemini model name, e.g., "models/gemini-1.5-pro".
    :param raw_data: A string containing raw data from a configuration management tool.
    :param prompt_instructions: Instructions appended to the raw data for summarization.
    :return: LLM-generated summary text.
    """
    model = genai.GenerativeModel(model_name)
    prompt = f"{prompt_instructions}\n\n--- RAW DATA START ---\n{raw_data}\n--- RAW DATA END ---\n"
    response = model.generate_content(prompt)
    return response.text


###############################################################################
# 2. Ansible Tower (AWX) – Data Retrieval & Summarization
###############################################################################

def fetch_ansible_data(
    tower_url: str,
    tower_token: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from Ansible Tower or AWX via its API.
    Typical data retrieved:
      - Inventories
      - Job templates
      - Recent job runs

    :param tower_url: Base URL for Ansible Tower (e.g., "https://tower.example.com").
    :param tower_token: Personal access token or OAuth token with appropriate permissions.
    :param verify_ssl: Whether to verify SSL certificates.
    :return: A dictionary with structured information about Ansible Tower resources.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {tower_token}"
    }

    # Fetch Inventories
    inv_url = f"{tower_url}/api/v2/inventories/"
    inventories_resp = requests.get(inv_url, headers=headers, verify=verify_ssl)
    inventories_resp.raise_for_status()
    inventories = inventories_resp.json()

    # Fetch Job Templates
    jt_url = f"{tower_url}/api/v2/job_templates/"
    job_templates_resp = requests.get(jt_url, headers=headers, verify=verify_ssl)
    job_templates_resp.raise_for_status()
    job_templates = job_templates_resp.json()

    # Fetch Recent Jobs (optional example)
    jobs_url = f"{tower_url}/api/v2/jobs/?order_by=-finished"
    recent_jobs_resp = requests.get(jobs_url, headers=headers, verify=verify_ssl)
    recent_jobs_resp.raise_for_status()
    recent_jobs = recent_jobs_resp.json()

    return {
        "inventories": inventories.get("results", []),
        "job_templates": job_templates.get("results", []),
        "recent_jobs": recent_jobs.get("results", [])
    }

def summarize_ansible_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Ansible Tower data using Gemini.

    :param credentials: Dict with "tower_url", "tower_token", "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Ansible Tower resources.
    """
    # 1. Fetch data from Ansible Tower
    ansible_data = fetch_ansible_data(
        tower_url=credentials["tower_url"],
        tower_token=credentials["tower_token"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert retrieved data to JSON for clarity
    ansible_data_str = json.dumps(ansible_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for Ansible Tower (AWX). "
        "Please provide a concise but comprehensive summary of the following data, "
        "including details on:\n"
        "• Inventories\n"
        "• Job Templates\n"
        "• Recent Jobs (status, success/failure)\n"
        "Format the summary in a readable form, highlighting any unusual items or errors."
    )

    # 5. Summarize using Gemini
    summary = summarize_with_llm(model_name, ansible_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. Chef Server – Data Retrieval & Summarization
###############################################################################

def fetch_chef_data(
    chef_server_url: str,
    client_key_path: str,
    client_name: str
) -> Dict[str, Any]:
    """
    Fetch data from a Chef Server using the pychef library.
    Typical data:
      - Cookbooks
      - Nodes (with run lists)
      - Roles or Policies

    :param chef_server_url: URL of the Chef Server (e.g., "https://chef-server.example.com/organizations/myorg").
    :param client_key_path: Path to the client.pem private key file.
    :param client_name: The client (user) name for authentication.
    :return: Dictionary with Chef resources (cookbooks, nodes, etc.).
    """
    # Initialize ChefAPI context
    with chef.ChefAPI(chef_server_url, client_key_path, client_name):
        # Gather cookbooks
        all_cookbooks = chef.Cookbook.list()
        cookbooks_data = {name: str(cookbook) for name, cookbook in all_cookbooks.items()}

        # Gather nodes
        all_nodes = chef.Node.list()
        nodes_data = {}
        for node_name in all_nodes:
            node_obj = chef.Node(node_name)
            nodes_data[node_name] = {
                "run_list": node_obj.run_list,
                "automatic_attrs": dict(node_obj.automatic)  # e.g., OS, IP, etc.
            }

        # Gather roles (or policies)
        all_roles = chef.Role.list()
        roles_data = {}
        for role_name in all_roles:
            role_obj = chef.Role(role_name)
            roles_data[role_name] = {
                "description": role_obj.description,
                "run_list": role_obj.run_list,
            }

    return {
        "cookbooks": cookbooks_data,
        "nodes": nodes_data,
        "roles": roles_data
    }

def summarize_chef_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Chef configuration data using Gemini.

    :param credentials: Dict with "chef_server_url", "client_key_path", "client_name".
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Chef data (cookbooks, nodes, roles).
    """
    # 1. Fetch data from Chef
    chef_data = fetch_chef_data(
        chef_server_url=credentials["chef_server_url"],
        client_key_path=credentials["client_key_path"],
        client_name=credentials["client_name"]
    )

    # 2. Convert to JSON
    chef_data_str = json.dumps(chef_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert in Chef configuration management. Summarize the following data with "
        "particular focus on:\n"
        "1. Cookbooks (notable contents, versioning, or unique items)\n"
        "2. Nodes (operating system, run lists, special attributes)\n"
        "3. Roles or Policies\n"
        "Highlight any anomalies or interesting points in a clear, organized structure."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, chef_data_str, prompt_instructions)
    return summary


###############################################################################
# 4. PuppetDB – Data Retrieval & Summarization
###############################################################################

def fetch_puppet_data(
    puppetdb_url: str,
    puppet_token: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from PuppetDB using its REST API.
    Typical data:
      - Nodes
      - Facts (OS, IP addresses, etc.)
      - Recent reports

    :param puppetdb_url: Base URL for PuppetDB (e.g., "https://puppetdb.example.com:8081").
    :param puppet_token: Authentication token for PuppetDB.
    :param verify_ssl: Whether to verify SSL certificates.
    :return: Dictionary of structured Puppet data.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Authentication": puppet_token
    }

    # Fetch a list of nodes
    nodes_endpoint = f"{puppetdb_url}/pdb/query/v4/nodes"
    nodes_resp = requests.get(nodes_endpoint, headers=headers, verify=verify_ssl)
    nodes_resp.raise_for_status()
    nodes = nodes_resp.json()

    # Fetch recent reports (example: last 5)
    # The 'reports' endpoint or related queries can vary by PuppetDB version
    reports_endpoint = f"{puppetdb_url}/pdb/query/v4/reports"
    reports_params = {
        "limit": 5,
        "order_by": '[{"field": "end_time", "order": "desc"}]'
    }
    reports_resp = requests.get(reports_endpoint, headers=headers, params=reports_params, verify=verify_ssl)
    reports_resp.raise_for_status()
    reports = reports_resp.json()

    # Potentially fetch facts or other relevant data
    facts_endpoint = f"{puppetdb_url}/pdb/query/v4/facts"
    facts_resp = requests.get(facts_endpoint, headers=headers, verify=verify_ssl)
    facts_resp.raise_for_status()
    facts = facts_resp.json()

    return {
        "nodes": nodes,
        "recent_reports": reports,
        "facts": facts
    }

def summarize_puppet_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Puppet data using Gemini.

    :param credentials: Dict with "puppetdb_url", "puppet_token", "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Puppet data.
    """
    # 1. Fetch data from PuppetDB
    puppet_data = fetch_puppet_data(
        puppetdb_url=credentials["puppetdb_url"],
        puppet_token=credentials["puppet_token"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert to JSON
    puppet_data_str = json.dumps(puppet_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for Puppet configuration data. "
        "Provide a concise summary that includes:\n"
        "• Nodes and any notable attributes\n"
        "• Recent Reports (changes, failures, etc.)\n"
        "• Facts (e.g., OS, IP addresses)\n"
        "Highlight errors or unusual findings in a clear structure."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, puppet_data_str, prompt_instructions)
    return summary


###############################################################################
# 5. Example Main
###############################################################################

if __name__ == "__main__":
    # Example: Realistic credentials for each system
    ansible_credentials = {
        "tower_url": "https://tower.example.com",
        "tower_token": "my-ansible-tower-token",
        "verify_ssl": True
    }

    chef_credentials = {
        "chef_server_url": "https://chef-server.example.com/organizations/myorg",
        "client_key_path": "/etc/chef/client.pem",
        "client_name": "devops-admin"
    }

    puppet_credentials = {
        "puppetdb_url": "https://puppetdb.example.com:8081",
        "puppet_token": "my-puppet-token",
        "verify_ssl": False  # Example where SSL verification is disabled
    }

    # Replace this with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Summarize data from Ansible Tower
    ansible_summary = summarize_ansible_data(ansible_credentials, GEMINI_API_KEY)
    print("===== ANSIBLE TOWER SUMMARY =====")
    print(ansible_summary)
    print()

    # Summarize data from Chef
    chef_summary = summarize_chef_data(chef_credentials, GEMINI_API_KEY)
    print("===== CHEF SUMMARY =====")
    print(chef_summary)
    print()

    # Summarize data from PuppetDB
    puppet_summary = summarize_puppet_data(puppet_credentials, GEMINI_API_KEY)
    print("===== PUPPET SUMMARY =====")
    print(puppet_summary)
