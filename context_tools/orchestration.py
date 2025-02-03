"""
Kubernetes & Docker Swarm - Data Retrieval & Summarization (No Environment-Based Config)

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. Kubernetes:
   - We only support two approaches (no 'kubeconfig_dict'):

   Option A) Using an existing kubeconfig file (typical in dev or ops):
       {
           "kubeconfig_path": "/path/to/kubeconfig"
       }

   Option B) Using direct token/host credentials:
       {
           "host": "https://k8s.example.com",
           "bearer_token": "abc123",
           "certificate_authority": "/path/to/ca.crt",  # optional
           "verify_ssl": True                          # optional, default True
       }

   The script will load or build the necessary Python Kubernetes client config, then fetch
   cluster info (deployments, services, pods, etc.) across namespaces.

2. Docker Swarm:
   - Provide direct parameters to connect to a **Swarm manager node**:

     swarm_credentials = {
         "base_url": "tcp://1.2.3.4:2376",   # e.g. your manager node
         "version": "1.41",                 # Docker API version
         "timeout": 60,                     # request timeout in seconds
         "tls_config": {
             "verify": True,
             "ca_cert": "/path/to/ca.pem",
             "client_cert": ("/path/to/cert.pem", "/path/to/key.pem")
         }
     }

   - If your Swarm manager doesn't use TLS, you might omit or adjust 'tls_config' accordingly.
   - This script does not automatically perform 'docker login' for private registries. If
     you need private image authentication, you can adapt the code to call 'login' or ensure
     your swarm is already configured to pull private images.

3. Gemini LLM API Key:
   - A valid API key for Google's Generative AI service (Gemini). Provide as a string.

--------------------------------------------------------------------------------
"""

import json
import os
import ssl
import requests
from typing import Dict, Any, Optional

# Kubernetes Python client
try:
    from kubernetes import client as k8s_client
    from kubernetes import config as k8s_config
except ImportError:
    raise ImportError(
        "The 'kubernetes' Python package is required. Install via 'pip install kubernetes'."
    )

# Docker Python client (for Docker Swarm)
import docker
from docker import tls as docker_tls

# For Google Generative AI (Gemini)
import google.generativeai as genai


###############################################################################
# Utility: Configure Gemini
###############################################################################

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

    :param model_name: The Gemini model name, e.g. "models/gemini-1.5-pro".
    :param raw_data: A string containing raw data to be summarized.
    :param prompt_instructions: Instructions appended to the raw data for summarization.
    :return: LLM-generated summary text.
    """
    model = genai.GenerativeModel(model_name)
    prompt = f"{prompt_instructions}\n\n--- RAW DATA START ---\n{raw_data}\n--- RAW DATA END ---\n"
    response = model.generate_content(prompt)
    return response.text


###############################################################################
# 1. Kubernetes - Data Retrieval & Summarization
###############################################################################

def build_k8s_client(credentials: Dict[str, Any]) -> k8s_client.ApiClient:
    """
    Build a Kubernetes ApiClient from given credentials, with no reliance on
    environment-based config. Two options are supported:

      A) {"kubeconfig_path": "/path/to/kubeconfig"}
      B) {
           "host": "https://k8s.example.com",
           "bearer_token": "abc123",
           "certificate_authority": "/path/to/ca.crt",
           "verify_ssl": True
         }

    :param credentials: Dict describing how to connect to the cluster.
    :return: An authenticated k8s_client.ApiClient instance.
    """
    if "kubeconfig_path" in credentials:
        # Load from a kubeconfig file
        k8s_config.load_kube_config(config_file=credentials["kubeconfig_path"])
        return k8s_client.ApiClient()

    elif "host" in credentials and "bearer_token" in credentials:
        # Direct config with host + bearer token (and optional CA)
        cfg = k8s_client.Configuration()
        cfg.host = credentials["host"]
        cfg.verify_ssl = credentials.get("verify_ssl", True)

        # If certificate_authority is provided, set it
        if credentials.get("certificate_authority"):
            cfg.ssl_ca_cert = credentials["certificate_authority"]

        # Set token for authentication
        cfg.api_key = {"authorization": f"Bearer {credentials['bearer_token']}"}
        cfg.api_key_prefix = {"authorization": "Bearer"}

        return k8s_client.ApiClient(configuration=cfg)

    else:
        raise ValueError(
            "Kubernetes credentials dict must have either 'kubeconfig_path' or "
            "'(host, bearer_token)' fields."
        )


def fetch_k8s_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data from Kubernetes. Typical data retrieved:
      - Namespaces
      - Deployments
      - Services
      - Pods
      - ConfigMaps

    :param credentials: Kubernetes connection parameters.
    :return: A dictionary with structured Kubernetes information.
    """
    api_client = build_k8s_client(credentials)
    core_v1 = k8s_client.CoreV1Api(api_client)
    apps_v1 = k8s_client.AppsV1Api(api_client)

    # Gather namespaces
    ns_list = core_v1.list_namespace()
    namespaces = [ns.metadata.name for ns in ns_list.items]

    # Gather deployments across all namespaces
    all_deployments = []
    for ns in namespaces:
        try:
            dep_list = apps_v1.list_namespaced_deployment(ns)
            for dep in dep_list.items:
                all_deployments.append({
                    "namespace": ns,
                    "name": dep.metadata.name,
                    "replicas": dep.spec.replicas,
                    "available_replicas": dep.status.available_replicas,
                    "labels": dep.metadata.labels,
                })
        except k8s_client.ApiException as e:
            # Some namespaces might be inaccessible or have no deployments
            if e.status not in (403, 404):
                raise

    # Gather services across all namespaces
    all_services = []
    for ns in namespaces:
        try:
            svc_list = core_v1.list_namespaced_service(ns)
            for svc in svc_list.items:
                all_services.append({
                    "namespace": ns,
                    "name": svc.metadata.name,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip,
                    "ports": [
                        {
                            "port": p.port,
                            "targetPort": p.target_port,
                            "protocol": p.protocol,
                        } for p in svc.spec.ports
                    ],
                    "labels": svc.metadata.labels,
                })
        except k8s_client.ApiException as e:
            if e.status not in (403, 404):
                raise

    # Gather pods across all namespaces
    all_pods = []
    for ns in namespaces:
        try:
            pod_list = core_v1.list_namespaced_pod(ns)
            for pod in pod_list.items:
                all_pods.append({
                    "namespace": ns,
                    "name": pod.metadata.name,
                    "phase": pod.status.phase,
                    "node_name": pod.spec.node_name,
                    "containers": [c.name for c in pod.spec.containers],
                    "labels": pod.metadata.labels,
                })
        except k8s_client.ApiException as e:
            if e.status not in (403, 404):
                raise

    # Gather configmaps across all namespaces
    all_configmaps = []
    for ns in namespaces:
        try:
            cm_list = core_v1.list_namespaced_config_map(ns)
            for cm in cm_list.items:
                all_configmaps.append({
                    "namespace": ns,
                    "name": cm.metadata.name,
                    "data_keys": list(cm.data.keys()) if cm.data else [],
                })
        except k8s_client.ApiException as e:
            if e.status not in (403, 404):
                raise

    return {
        "namespaces": namespaces,
        "deployments": all_deployments,
        "services": all_services,
        "pods": all_pods,
        "configmaps": all_configmaps,
    }


def summarize_k8s_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Kubernetes data using Gemini.

    :param credentials: K8s connection parameters (either kubeconfig_path or host/bearer_token).
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Kubernetes resources.
    """
    # 1. Fetch data from Kubernetes
    k8s_data = fetch_k8s_data(credentials)

    # 2. Convert to JSON
    k8s_data_str = json.dumps(k8s_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert in Kubernetes orchestration. Summarize the following data with focus on:\n"
        "• Deployments (replicas vs. available replicas)\n"
        "• Services (types, ports)\n"
        "• Pods (status, node assignment, container count)\n"
        "• ConfigMaps (noteworthy config data)\n"
        "• Any anomalies or potential issues (e.g., pods not running)\n"
        "Provide a concise, structured summary to help an AI agent make decisions."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, k8s_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. Docker Swarm - Data Retrieval & Summarization
###############################################################################

def build_swarm_client(credentials: Dict[str, Any]) -> docker.DockerClient:
    """
    Build a DockerClient specifically for connecting to a Docker Swarm manager node,
    with no reliance on environment-based config.

    :param credentials: Docker swarm manager connection parameters. Example:
         {
             "base_url": "tcp://1.2.3.4:2376",
             "version": "1.41",
             "timeout": 60,
             "tls_config": {
                 "verify": True,
                 "ca_cert": "/path/to/ca.pem",
                 "client_cert": ("/path/to/cert.pem", "/path/to/key.pem")
             }
         }
    :return: docker.DockerClient instance connected to the manager node.
    """
    base_url = credentials["base_url"]  # e.g. "tcp://1.2.3.4:2376"
    version = credentials.get("version", None)
    timeout = credentials.get("timeout", 60)

    tls_conf = None
    tls_dict = credentials.get("tls_config")
    if type(tls_dict) == str:
        tls_dict = json.loads(tls_dict)
    if tls_dict:
        tls_conf = docker_tls.TLSConfig(
            client_cert=tls_dict.get("client_cert"),
            ca_cert=tls_dict.get("ca_cert"),
            verify=tls_dict.get("verify", True),
            ssl_version=tls_dict.get("ssl_version", ssl.PROTOCOL_TLSv1_2),
            assert_hostname=tls_dict.get("assert_hostname", True),
        )

    client = docker.DockerClient(
        base_url=base_url,
        version=version,
        timeout=timeout,
        tls=tls_conf
    )

    return client


def fetch_swarm_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data from a Docker Swarm manager node, typically:
      - Swarm info
      - Services
      - Nodes
      - Networks

    :param credentials: Docker swarm manager connection parameters.
    :return: A dictionary with structured Swarm information.
    """
    client = build_swarm_client(credentials)

    # Check Swarm info
    swarm_info = {}
    try:
        swarm_info = client.swarm.attrs
    except docker.errors.APIError as e:
        # If the daemon is not in swarm mode, handle or raise
        if e.explanation:
            raise RuntimeError(f"Failed to retrieve swarm info: {e.explanation}")

    # List services
    services_data = []
    services = client.services.list()
    for svc in services:
        services_data.append({
            "id": svc.id,
            "name": svc.name,
            "image": svc.attrs.get("Spec", {}).get("TaskTemplate", {}).get("ContainerSpec", {}).get("Image"),
            "replicas": svc.attrs.get("Spec", {}).get("Mode", {}).get("Replicated", {}).get("Replicas"),
            "ports": svc.attrs.get("Endpoint", {}).get("Ports", []),
        })

    # List nodes
    nodes_data = []
    nodes = client.nodes.list()
    for node in nodes:
        nodes_data.append({
            "id": node.id,
            "hostname": node.attrs["Description"]["Hostname"],
            "role": node.attrs["Spec"].get("Role"),
            "availability": node.attrs["Spec"].get("Availability"),
            "state": node.attrs["Status"].get("State"),
            "addr": node.attrs["Status"].get("Addr"),
        })

    # List networks (primarily for overlay networks used by swarm services)
    networks_data = []
    networks = client.networks.list()
    for net in networks:
        networks_data.append({
            "id": net.id,
            "name": net.name,
            "driver": net.attrs.get("Driver"),
            "scope": net.attrs.get("Scope"),
        })

    return {
        "swarm_info": swarm_info,
        "services": services_data,
        "nodes": nodes_data,
        "networks": networks_data,
    }


def summarize_swarm_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Docker Swarm data using Gemini.

    :param credentials: Docker swarm manager connection parameters.
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Swarm resources.
    """
    # 1. Fetch data from Swarm
    swarm_data = fetch_swarm_data(credentials)

    # 2. Convert to JSON
    swarm_data_str = json.dumps(swarm_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for Docker Swarm clusters. Provide a concise summary that covers:\n"
        "• Swarm info (Cluster ID, creation date, etc.)\n"
        "• Services (images, replicas, ports)\n"
        "• Nodes (role, availability, status)\n"
        "• Networks (particularly overlay)\n"
        "Highlight any unusual configurations, errors, or interesting findings."
    )

    # 5. Summarize using Gemini
    summary = summarize_with_llm(model_name, swarm_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. Example Main
###############################################################################

if __name__ == "__main__":
    # Kubernetes credentials example (Option A: kubeconfig file)
    k8s_credentials = {
        "kubeconfig_path": "/path/to/kubeconfig"
    }
    # OR (Option B: direct host/token):
    # k8s_credentials = {
    #     "host": "https://my-k8s.example.com",
    #     "bearer_token": "abc123",
    #     "certificate_authority": "/path/to/ca.crt",
    #     "verify_ssl": True
    # }

    # Docker Swarm manager credentials example:
    swarm_credentials = {
        "base_url": "tcp://1.2.3.4:2376",
        "version": "1.41",
        "timeout": 60,
        "tls_config": {
            "verify": True,
            "ca_cert": "/path/to/ca.pem",
            "client_cert": ("/path/to/cert.pem", "/path/to/key.pem")
        }
    }

    # Replace with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    print("===== KUBERNETES SUMMARY =====")
    k8s_summary = summarize_k8s_data(k8s_credentials, GEMINI_API_KEY)
    print(k8s_summary)
    print()

    print("===== DOCKER SWARM SUMMARY =====")
    swarm_summary = summarize_swarm_data(swarm_credentials, GEMINI_API_KEY)
    print(swarm_summary)
