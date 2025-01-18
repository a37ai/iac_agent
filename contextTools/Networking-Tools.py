"""
Networking & Security – Data Retrieval & Summarization

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. Istio:
   Since Istio configurations (service meshes, security policies, etc.) reside in
   Kubernetes Custom Resource Definitions (CRDs), we connect to Kubernetes to read
   those CRDs. As with earlier K8s-based examples, provide one of:
       A) kubeconfig-based:
          {
            "kubeconfig_path": "/path/to/kubeconfig"
          }
       B) direct host/token approach:
          {
            "host": "https://k8s.example.com",
            "bearer_token": "my-token",
            "certificate_authority": "/path/to/ca.crt",
            "verify_ssl": True
          }
   We attempt to list relevant Istio CRDs:
     - VirtualService
     - DestinationRule
     - Gateway
     - PeerAuthentication
     - AuthorizationPolicy
   Summaries highlight traffic rules, security, and potential misconfigurations.

2. HashiCorp Consul:
   Provide:
     {
       "consul_url": "http://consul.example.com:8500",
       "token": "my-consul-acl-token",
       "verify_ssl": True
     }
   We query:
     - Catalog services (and their tags)
     - Health checks for those services
     - Possibly some KV store keys or Consul configuration
   Summaries focus on service discovery, configuration, and network segmentation.

3. Gemini LLM API Key:
   Provide your Gemini API key as a string, e.g.:
       GEMINI_API_KEY = "your-api-key"

--------------------------------------------------------------------------------
DEPENDENCIES:
   pip install kubernetes
   pip install requests
   pip install google-generativeai
--------------------------------------------------------------------------------
"""

import json
import os
import ssl
import requests
from typing import Dict, Any, Optional

# Kubernetes Python client for Istio CRDs
try:
    from kubernetes import client as k8s_client
    from kubernetes import config as k8s_config
except ImportError:
    print("WARNING: Kubernetes Python client is required (pip install kubernetes) for Istio data.")
    k8s_client = None

# For Google Generative AI (Gemini)
try:
    import google.generativeai as genai
except ImportError:
    print("WARNING: google-generativeai is required for summarization (pip install google-generativeai)")
    genai = None


###############################################################################
# Utility: Configure Gemini & Summarization
###############################################################################

def configure_llm(api_key: str):
    """
    Configure the Google Generative AI client to use the specified API key.
    """
    if not genai:
        raise ImportError("Gemini library not installed or not imported properly.")
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
    if not genai:
        raise ImportError("Gemini library not installed or not imported properly.")
    model = genai.GenerativeModel(model_name)
    prompt = f"{prompt_instructions}\n\n--- RAW DATA START ---\n{raw_data}\n--- RAW DATA END ---\n"
    response = model.generate_content(prompt)
    return response.text


###############################################################################
# 1. Istio (via Kubernetes CRDs) – Data Retrieval & Summarization
###############################################################################

def build_k8s_client(credentials: Dict[str, Any]) -> k8s_client.ApiClient:
    """
    Build a Kubernetes ApiClient from given credentials. Two supported modes:
      A) {"kubeconfig_path": "/path/to/kubeconfig"}
      B) {
          "host": "https://k8s.example.com",
          "bearer_token": "my-token",
          "certificate_authority": "/path/to/ca.crt",
          "verify_ssl": True
        }

    :param credentials: Dict describing how to connect to the cluster.
    :return: An authenticated k8s_client.ApiClient instance.
    """
    if not k8s_client:
        raise ImportError("Kubernetes library not installed properly.")

    if "kubeconfig_path" in credentials:
        k8s_config.load_kube_config(config_file=credentials["kubeconfig_path"])
        return k8s_client.ApiClient()
    elif "host" in credentials and "bearer_token" in credentials:
        cfg = k8s_client.Configuration()
        cfg.host = credentials["host"]
        cfg.verify_ssl = credentials.get("verify_ssl", True)

        if credentials.get("certificate_authority"):
            cfg.ssl_ca_cert = credentials["certificate_authority"]

        # Set token
        cfg.api_key = {"authorization": f"Bearer {credentials['bearer_token']}"}
        cfg.api_key_prefix = {"authorization": "Bearer"}

        return k8s_client.ApiClient(configuration=cfg)
    else:
        raise ValueError(
            "Istio credentials dict must have either 'kubeconfig_path' or "
            "'(host, bearer_token)' fields."
        )


def fetch_istio_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch Istio CRDs (VirtualService, DestinationRule, Gateway, PeerAuthentication, AuthorizationPolicy)
    from a Kubernetes cluster. Summaries of these objects help manage traffic rules, security, etc.

    :param credentials: K8s connection parameters
    :return: A dictionary containing lists of relevant Istio objects + any errors
    """
    api_client = build_k8s_client(credentials)
    data = {
        "virtual_services": [],
        "destination_rules": [],
        "gateways": [],
        "peer_authentications": [],
        "authorization_policies": [],
        "errors": []
    }

    # We need to access custom objects: group=networking.istio.io, security.istio.io, etc.
    # e.g. VirtualService -> group=networking.istio.io, version=v1beta1, plural=virtualservices
    # For the sake of example, we'll do v1beta1 or v1alpha1 as available

    custom_api = k8s_client.CustomObjectsApi(api_client)

    # Let's define some CRD queries
    # (In reality, Istio CRD versions can differ based on the installed version)
    crds = [
        {
            "name": "virtual_services",
            "group": "networking.istio.io",
            "version": "v1beta1",
            "plural": "virtualservices"
        },
        {
            "name": "destination_rules",
            "group": "networking.istio.io",
            "version": "v1beta1",
            "plural": "destinationrules"
        },
        {
            "name": "gateways",
            "group": "networking.istio.io",
            "version": "v1beta1",
            "plural": "gateways"
        },
        {
            "name": "peer_authentications",
            "group": "security.istio.io",
            "version": "v1beta1",
            "plural": "peerauthentications"
        },
        {
            "name": "authorization_policies",
            "group": "security.istio.io",
            "version": "v1beta1",
            "plural": "authorizationpolicies"
        }
    ]

    for crd in crds:
        name = crd["name"]
        group = crd["group"]
        version = crd["version"]
        plural = crd["plural"]

        try:
            # We list cluster-wide objects by specifying namespace=None
            # If needed, we can loop over namespaces or fetch from "all-namespaces"
            # Many Istio CRDs can be in multiple namespaces
            all_ns = custom_api.list_cluster_custom_object(group, version, plural)
            items = all_ns.get("items", [])
            data[name] = items
        except Exception as e:
            data["errors"].append(f"Failed to list {plural}: {str(e)}")

    return data


def summarize_istio_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Istio data using Gemini.

    :param credentials: K8s credentials (kubeconfig or host/token).
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Istio CRDs.
    """
    istio_data = fetch_istio_data(credentials)
    istio_data_str = json.dumps(istio_data, indent=2)

    configure_llm(api_key)
    prompt_instructions = (
        "You are an expert in Istio service mesh. Summarize the following data:\n"
        "• VirtualServices (host routing, HTTP/TLS rules)\n"
        "• DestinationRules (subsets, traffic policies)\n"
        "• Gateways (ingress/egress configs)\n"
        "• PeerAuthentications (mTLS settings)\n"
        "• AuthorizationPolicies (RBAC-like access rules)\n"
        "Highlight any misconfigurations, conflicting rules, or potential improvements. "
        "Mention errors if present."
    )

    summary = summarize_with_llm(model_name, istio_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. HashiCorp Consul – Data Retrieval & Summarization
###############################################################################

def fetch_consul_data(
    consul_url: str,
    token: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from a Consul server. Typical data:
      - Catalog Services
      - Health checks
      - Possibly some KV pairs or intentions (if using Connect)

    :param consul_url: Base URL for Consul (e.g. "http://consul.example.com:8500").
    :param token: ACL token if Consul is secured.
    :param verify_ssl: Whether to verify SSL certs (for https).
    :return: Dictionary of structured Consul data (services, checks, possible KV).
    """
    session = requests.Session()
    session.verify = verify_ssl
    # The X-Consul-Token header is used for ACL tokens
    session.headers.update({"X-Consul-Token": token})

    data = {
        "services": {},
        "service_health": {},
        "kv_sample": {},
        "errors": []
    }

    # 1) List all services
    # GET /v1/catalog/services
    services_endpoint = f"{consul_url}/v1/catalog/services"
    try:
        svc_resp = session.get(services_endpoint)
        svc_resp.raise_for_status()
        services_data = svc_resp.json()  # { "serviceName": ["tag1", "tag2"], ... }
        data["services"] = services_data
    except requests.RequestException as e:
        data["errors"].append(f"Failed to list services: {str(e)}")
        return data

    # 2) For each service, fetch health checks
    # GET /v1/health/checks/<serviceName>
    for svc_name in data["services"].keys():
        checks_endpoint = f"{consul_url}/v1/health/checks/{svc_name}"
        try:
            checks_resp = session.get(checks_endpoint)
            checks_resp.raise_for_status()
            checks_data = checks_resp.json()
            data["service_health"][svc_name] = checks_data
        except requests.RequestException as e:
            data["errors"].append(f"Failed to fetch health for {svc_name}: {str(e)}")

    # 3) Optionally fetch a sample of KV (just to see if there's interesting config)
    # GET /v1/kv/?keys
    # We'll list all keys, then fetch the first 3 if any.
    kv_keys_endpoint = f"{consul_url}/v1/kv/?keys"
    try:
        kv_keys_resp = session.get(kv_keys_endpoint)
        if kv_keys_resp.ok:
            kv_keys = kv_keys_resp.json()
            # fetch a sample of 3 keys
            for k in kv_keys[:3]:
                single_key_endpoint = f"{consul_url}/v1/kv/{k}"
                single_key_resp = session.get(single_key_endpoint)
                if single_key_resp.ok:
                    key_data = single_key_resp.json()
                    data["kv_sample"][k] = key_data
                else:
                    data["errors"].append(
                        f"Failed to retrieve value for key {k}. Status: {single_key_resp.status_code}"
                    )
        else:
            data["errors"].append(f"Failed to list KV keys. Status code: {kv_keys_resp.status_code}")
    except requests.RequestException as e:
        data["errors"].append(f"KV listing error: {str(e)}")

    return data


def summarize_consul_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Consul data using Gemini.

    :param credentials: Dict with "consul_url", "token", "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Consul services, health checks, KV samples.
    """
    consul_data = fetch_consul_data(
        consul_url=credentials["consul_url"],
        token=credentials["token"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    consul_data_str = json.dumps(consul_data, indent=2)
    configure_llm(api_key)

    prompt_instructions = (
        "You are an expert in HashiCorp Consul service discovery and configuration. Summarize:\n"
        "• Services (names, tags)\n"
        "• Health checks (passing/failing)\n"
        "• KV sample (common config keys)\n"
        "• Any errors\n"
        "Highlight potential issues, unusual configurations, or best practices for network segmentation and service management."
    )

    summary = summarize_with_llm(model_name, consul_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. Example Main
###############################################################################

if __name__ == "__main__":
    # Istio (K8s) Credentials Example
    istio_credentials = {
        # Option A: Provide a kubeconfig path
        "kubeconfig_path": "/path/to/kubeconfig"

        # OR Option B:
        # "host": "https://k8s.example.com",
        # "bearer_token": "my-token",
        # "certificate_authority": "/path/to/ca.crt",
        # "verify_ssl": True
    }

    # HashiCorp Consul Credentials Example
    consul_credentials = {
        "consul_url": "http://consul.example.com:8500",
        "token": "my-consul-acl-token",
        "verify_ssl": False
    }

    # Replace with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    # Summarize Istio Data
    print("===== ISTIO SUMMARY =====")
    try:
        istio_summary = summarize_istio_data(istio_credentials, GEMINI_API_KEY)
        print(istio_summary)
    except Exception as e:
        print(f"Error summarizing Istio: {e}")
    print()

    # Summarize Consul Data
    print("===== CONSUL SUMMARY =====")
    try:
        consul_summary = summarize_consul_data(consul_credentials, GEMINI_API_KEY)
        print(consul_summary)
    except Exception as e:
        print(f"Error summarizing Consul: {e}")
    print()
