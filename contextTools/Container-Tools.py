"""
Docker & Podman – Data Retrieval & Summarization (No Environment-Based Config)

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. Docker:
   - base_url (str): Docker daemon address. For local: "unix://var/run/docker.sock"
                     For remote: "tcp://<IP or hostname>:2376"
   - version (str, optional): Docker API version (e.g., "1.41"). Can be omitted.
   - timeout (int, optional): Timeout in seconds (default 60).
   - tls_config (dict, optional): For TLS-protected remote Docker. Possible keys:
        {
            "verify": bool,              # True/False
            "ssl_version": <ssl.PROTOCOL_* constant>,  # e.g. ssl.PROTOCOL_TLSv1_2
            "assert_hostname": bool,     # If you want to disable hostname checking
            "ca_cert": str,              # Path to CA certificate
            "client_cert": Tuple[str, str]  # (path_to_cert.pem, path_to_key.pem)
        }
   - registry_auth (dict, optional): For authenticating to a registry before pulling images, etc.
        {
            "username": str,
            "password": str,
            "registry": str  # e.g. "https://index.docker.io/v1/" or your private registry
        }

   This script won't automatically store your credentials in config.json or a credential
   store. Instead, it will:
     1. Connect to the Docker daemon using base_url (and TLS if needed).
     2. Optionally call `client.login()` with your registry credentials
        (useful if the AI agent needs to pull private images or otherwise requires auth).

   Example Docker credentials dict:

   docker_credentials = {
       "base_url": "tcp://1.2.3.4:2376",
       "version": "1.41",
       "timeout": 60,
       "tls_config": {
           "verify": True,
           "ca_cert": "/path/to/ca.pem",
           "client_cert": ("/path/to/cert.pem", "/path/to/key.pem")
       },
       "registry_auth": {
           "username": "myuser",
           "password": "mypassword123",
           "registry": "https://index.docker.io/v1/"
       }
   }

2. Podman:
   - podman_url (str): Base URL for the Podman service (e.g., "http://localhost:8080").
   - auth_token (str, optional): Authentication token if Podman service requires it.
   - verify_ssl (bool): Whether to verify SSL certificates.

   Example Podman credentials dict:
   podman_credentials = {
       "podman_url": "http://localhost:8080",
       "auth_token": "",
       "verify_ssl": False
   }

3. Gemini LLM API Key:
   - A valid API key for Google's Generative AI service (Gemini). Used for summarization.
     Provide this as a string, or retrieve from secure storage.

   GEMINI_API_KEY = "your-api-key"

NOTE: This script is designed for an automated agent. Users typically won't manually
enter credentials. The AI agent can securely fetch them from a vault or a secrets manager.

--------------------------------------------------------------------------------
"""

import json
import os
import ssl
import requests
from typing import Dict, Any, Optional, Tuple

import docker
from docker import tls as docker_tls

# For Google Generative AI (Gemini)
import google.generativeai as genai


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
# 1. Docker – Data Retrieval & Summarization
###############################################################################

def build_docker_client(credentials: Dict[str, Any]) -> docker.DockerClient:
    """
    Build a DockerClient using direct parameters (no environment-based config).
    Optionally logs in to a registry if 'registry_auth' is provided.

    :param credentials: Docker connection parameters (see docstring).
    :return: docker.DockerClient instance.
    """
    base_url = credentials["base_url"]  # Required
    version = credentials.get("version", None)
    timeout = credentials.get("timeout", 60)

    tls_conf = None
    tls_dict = credentials.get("tls_config")
    if tls_dict:
        # Example structure:
        # tls_dict = {
        #    "verify": True,
        #    "ca_cert": "/path/to/ca.pem",
        #    "client_cert": ("/path/to/cert.pem", "/path/to/key.pem"),
        #    "ssl_version": ssl.PROTOCOL_TLSv1_2,
        #    "assert_hostname": False
        # }
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

    # Optional registry login if credentials are provided
    registry_auth = credentials.get("registry_auth")
    if registry_auth:
        try:
            # For example:
            # "registry_auth": {
            #     "username": "myuser",
            #     "password": "mypassword123",
            #     "registry": "https://index.docker.io/v1/"
            # }
            api_client = client.api  # Low-level APIClient
            api_client.login(
                username=registry_auth["username"],
                password=registry_auth["password"],
                registry=registry_auth.get("registry", "https://index.docker.io/v1/")
            )
        except docker.errors.APIError as e:
            raise RuntimeError(f"Failed to login to Docker registry: {e.explanation}")

    return client


def fetch_docker_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data from a Docker engine. Typical data retrieved:
      - Containers (running & stopped)
      - Images
      - Networks
      - Volumes

    :param credentials: Docker connection parameters (see docstring).
    :return: A dictionary with structured Docker information.
    """
    # Create the Docker client (with optional registry login)
    client = build_docker_client(credentials)

    # Fetch containers (all=True means include stopped containers)
    containers = client.containers.list(all=True)
    container_info = []
    for c in containers:
        container_info.append({
            "id": c.id,
            "name": c.name,
            "image": c.image.tags,
            "status": c.status,
            "ports": c.attrs.get("NetworkSettings", {}).get("Ports", {}),
        })

    # Fetch images
    images = client.images.list()
    image_info = []
    for img in images:
        image_info.append({
            "id": img.id,
            "tags": img.tags,
            "created": getattr(img, "attrs", {}).get("Created", ""),
            "size": getattr(img, "attrs", {}).get("Size", 0),
        })

    # Fetch networks
    networks = client.networks.list()
    network_info = []
    for net in networks:
        network_info.append({
            "id": net.id,
            "name": net.name,
            "driver": net.attrs.get("Driver"),
            "scope": net.attrs.get("Scope"),
            "containers": net.attrs.get("Containers", {}),
        })

    # Fetch volumes
    volumes_list = client.volumes.list()
    volume_info = []
    for vol in volumes_list:
        volume_info.append({
            "name": vol.name,
            "mountpoint": vol.attrs.get("Mountpoint"),
            "scope": vol.attrs.get("Scope"),
            "labels": vol.attrs.get("Labels", {}),
        })

    return {
        "containers": container_info,
        "images": image_info,
        "networks": network_info,
        "volumes": volume_info
    }


def summarize_docker_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Docker data using Gemini.

    :param credentials: Docker daemon + (optional) registry authentication details.
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Docker resources.
    """
    # 1. Fetch data from Docker
    docker_data = fetch_docker_data(credentials)

    # 2. Convert to JSON for clarity
    docker_data_str = json.dumps(docker_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for Docker environments. Please provide a concise but "
        "comprehensive summary of the following data, focusing on:\n"
        "• Containers (status, image, exposed ports)\n"
        "• Images (tags, size, duplicates)\n"
        "• Networks (driver, scope, attached containers)\n"
        "• Volumes (naming conventions, usage)\n"
        "Highlight any unusual configurations, errors, or potential improvements. "
        "Assume the user has provided registry credentials if needed for private images."
    )

    # 5. Summarize using Gemini
    summary = summarize_with_llm(model_name, docker_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. Podman – Data Retrieval & Summarization
###############################################################################

def fetch_podman_data(
    podman_url: str,
    auth_token: str = "",
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from a Podman service using its REST API.
    Typical data includes:
      - Containers
      - Images
      - Pods (if any)
      - Networks (optional)
      - Volumes (optional)

    :param podman_url: Base URL for the Podman service, e.g., "http://localhost:8080".
    :param auth_token: Optional authentication token if the Podman service requires it.
    :param verify_ssl: Whether to verify SSL certificates.
    :return: Dictionary of structured Podman data.
    """
    headers = {
        "Content-Type": "application/json"
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    session = requests.Session()
    session.verify = verify_ssl

    # Fetch containers
    containers_endpoint = f"{podman_url}/v4.0.0/libpod/containers/json?all=true"
    containers_resp = session.get(containers_endpoint, headers=headers)
    containers_resp.raise_for_status()
    containers_data = containers_resp.json()

    # Fetch images
    images_endpoint = f"{podman_url}/v4.0.0/libpod/images/json"
    images_resp = session.get(images_endpoint, headers=headers)
    images_resp.raise_for_status()
    images_data = images_resp.json()

    # Fetch pods
    pods_endpoint = f"{podman_url}/v4.0.0/libpod/pods/json?all=true"
    pods_resp = session.get(pods_endpoint, headers=headers)
    pods_resp.raise_for_status()
    pods_data = pods_resp.json()

    # Fetch networks (optional)
    networks_data = []
    networks_endpoint = f"{podman_url}/v4.0.0/libpod/networks/json"
    try:
        networks_resp = session.get(networks_endpoint, headers=headers)
        networks_resp.raise_for_status()
        networks_data = networks_resp.json()
    except requests.HTTPError:
        # Some Podman versions/installations might not have this endpoint
        pass

    # Fetch volumes (optional)
    volumes_data = {}
    volumes_endpoint = f"{podman_url}/v4.0.0/libpod/volumes/json"
    try:
        volumes_resp = session.get(volumes_endpoint, headers=headers)
        volumes_resp.raise_for_status()
        volumes_data = volumes_resp.json()
    except requests.HTTPError:
        # If volumes endpoint isn't supported or returns error, skip
        pass

    return {
        "containers": containers_data,
        "images": images_data,
        "pods": pods_data,
        "networks": networks_data,
        "volumes": volumes_data
    }


def summarize_podman_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Podman data using Gemini.

    :param credentials: Dict with "podman_url", "auth_token", "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Podman data.
    """
    # 1. Fetch data from Podman
    podman_data = fetch_podman_data(
        podman_url=credentials["podman_url"],
        auth_token=credentials.get("auth_token", ""),
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert data to JSON
    podman_data_str = json.dumps(podman_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for Podman environments. Provide a concise summary that covers:\n"
        "• Containers (running/stopped, associated images, status)\n"
        "• Images (tags, size, duplicates)\n"
        "• Pods (composition, container statuses)\n"
        "• Networks\n"
        "• Volumes\n"
        "Highlight any unusual configurations, errors, or interesting findings."
    )

    # 5. Summarize using Gemini
    summary = summarize_with_llm(model_name, podman_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. Example Main
###############################################################################

if __name__ == "__main__":
    # Example credentials for Docker (direct parameters) - no environment usage
    docker_credentials = {
        "base_url": "tcp://1.2.3.4:2376",
        "version": "1.41",
        "timeout": 60,
        "tls_config": {
            "verify": True,
            "ca_cert": "/path/to/ca.pem",
            "client_cert": ("/path/to/cert.pem", "/path/to/key.pem"),
            # "ssl_version": ssl.PROTOCOL_TLSv1_2,
            # "assert_hostname": False,
        },
        # Registry login example:
        "registry_auth": {
            "username": "mydockeruser",
            "password": "mysecretpassword",
            "registry": "https://index.docker.io/v1/"
        }
    }

    # Example credentials for Podman
    podman_credentials = {
        "podman_url": "http://localhost:8080",
        "auth_token": "",
        "verify_ssl": False
    }

    # Replace with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    # Summarize Docker data
    docker_summary = summarize_docker_data(docker_credentials, GEMINI_API_KEY)
    print("===== DOCKER SUMMARY =====")
    print(docker_summary)
    print()

    # Summarize Podman data
    podman_summary = summarize_podman_data(podman_credentials, GEMINI_API_KEY)
    print("===== PODMAN SUMMARY =====")
    print(podman_summary)
