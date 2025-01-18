"""
Monitoring & Logging – Data Retrieval & Summarization

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. Prometheus:
   - Provide a dictionary like:
       {
           "prometheus_url": "http://prometheus.example.com:9090",
           "auth_token": "optional-bearer-or-basic-token",
           "verify_ssl": True
       }
   This script queries Prometheus for targets, alerts, and rules to provide a basic snapshot.

2. Grafana:
   - Provide a dictionary like:
       {
           "grafana_url": "http://grafana.example.com",
           "api_token": "my-secret-token",
           "verify_ssl": True
       }
   The script queries Grafana's API for dashboards and data sources.

3. ELK Stack (Elasticsearch, Logstash, Kibana):
   Since ELK is typically multiple components, we unify them here. Provide:
       {
           "elasticsearch_url": "http://es.example.com:9200",
           "es_username": "elastic",
           "es_password": "mypassword",
           
           "logstash_url": "http://logstash.example.com:9600",
           "logstash_username": "logstashuser",
           "logstash_password": "logstashpass",

           "kibana_url": "http://kibana.example.com:5601",
           "kibana_username": "kibanauser",
           "kibana_password": "kibanapass",

           "verify_ssl": True
       }
   If any of Elasticsearch, Logstash, or Kibana are omitted, that component’s data
   will be skipped. The script tries to gather cluster health & indices from ES,
   pipeline info from Logstash, and saved objects (dashboards/visualizations) from Kibana.

4. Datadog:
   - Provide a dictionary like:
       {
           "datadog_api_key": "my-datadog-api-key",
           "datadog_app_key": "my-datadog-app-key",
           "verify_ssl": True
       }
   The script queries Datadog’s API for monitors and dashboards.

5. Gemini LLM API Key:
   - Provide your Gemini API key as a string.

--------------------------------------------------------------------------------
"""

import json
import os
import requests
from typing import Dict, Any, Optional

# For Google Generative AI (Gemini)
import google.generativeai as genai


###############################################################################
# Utility: Configure Gemini & Summarization
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
# 1. Prometheus – Data Retrieval & Summarization
###############################################################################

def fetch_prometheus_data(
    prometheus_url: str,
    auth_token: Optional[str] = None,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from Prometheus. Typical data:
      - Targets
      - Alerts
      - Rules

    :param prometheus_url: Base URL for Prometheus (e.g., "http://localhost:9090").
    :param auth_token: Optional bearer token or basic auth token.
    :param verify_ssl: Whether to verify SSL certificates.
    :return: A dictionary of structured Prometheus data.
    """
    session = requests.Session()
    session.verify = verify_ssl

    if auth_token:
        # Could be a bearer token or "Basic <encoded>"
        session.headers.update({"Authorization": f"Bearer {auth_token}"})

    # 1. Targets
    targets_url = f"{prometheus_url}/api/v1/targets"
    targets_resp = session.get(targets_url)
    targets_resp.raise_for_status()
    targets_data = targets_resp.json()

    # 2. Alerts
    alerts_url = f"{prometheus_url}/api/v1/alerts"
    alerts_resp = session.get(alerts_url)
    alerts_resp.raise_for_status()
    alerts_data = alerts_resp.json()

    # 3. Rules
    rules_url = f"{prometheus_url}/api/v1/rules"
    rules_resp = session.get(rules_url)
    rules_resp.raise_for_status()
    rules_data = rules_resp.json()

    return {
        "targets": targets_data.get("data", {}),
        "alerts": alerts_data.get("data", {}),
        "rules": rules_data.get("data", {})
    }


def summarize_prometheus_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Prometheus data using Gemini.

    :param credentials: Dict with "prometheus_url", "auth_token", "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Prometheus info.
    """
    # 1. Fetch data
    prom_data = fetch_prometheus_data(
        prometheus_url=credentials["prometheus_url"],
        auth_token=credentials.get("auth_token"),
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert to JSON
    prom_data_str = json.dumps(prom_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert in Prometheus monitoring. Summarize the following data with focus on:\n"
        "• Active Targets (health, labels)\n"
        "• Alerts (firing, pending)\n"
        "• Rules (alerting or recording)\n"
        "Highlight anything unusual or problematic."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, prom_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. Grafana – Data Retrieval & Summarization
###############################################################################

def fetch_grafana_data(
    grafana_url: str,
    api_token: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from Grafana. Typical data:
      - Dashboards
      - Data sources

    :param grafana_url: Base URL for Grafana (e.g., "http://grafana.example.com").
    :param api_token: API token with read privileges.
    :param verify_ssl: Whether to verify SSL certs.
    :return: A dictionary of Grafana resources.
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.headers.update({"Authorization": f"Bearer {api_token}"})

    # 1. Dashboards (search all, limited example)
    dashboards_url = f"{grafana_url}/api/search?type=dash-db"
    dash_resp = session.get(dashboards_url)
    dash_resp.raise_for_status()
    dashboards_data = dash_resp.json()

    # 2. Data sources
    datasources_url = f"{grafana_url}/api/datasources"
    ds_resp = session.get(datasources_url)
    ds_resp.raise_for_status()
    datasources_data = ds_resp.json()

    return {
        "dashboards": dashboards_data,
        "datasources": datasources_data
    }


def summarize_grafana_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Grafana data using Gemini.

    :param credentials: Dict with "grafana_url", "api_token", "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Grafana resources.
    """
    # 1. Fetch data
    graf_data = fetch_grafana_data(
        grafana_url=credentials["grafana_url"],
        api_token=credentials["api_token"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert to JSON
    graf_data_str = json.dumps(graf_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert in Grafana dashboards and data sources. Summarize the following data:\n"
        "• Dashboards (titles, any notable features)\n"
        "• Data sources (types, usage)\n"
        "Highlight anomalies, duplicates, or potential improvements."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, graf_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. ELK Stack – Data Retrieval & Summarization
###############################################################################

def fetch_elk_data(
    elk_credentials: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fetch data from the ELK stack (Elasticsearch, Logstash, Kibana).
    Provided keys in 'elk_credentials' may include:
      - "elasticsearch_url", "es_username", "es_password"
      - "logstash_url", "logstash_username", "logstash_password"
      - "kibana_url", "kibana_username", "kibana_password"
      - "verify_ssl" (bool)
    We'll attempt each component if its URL is provided.

    :return: A dictionary with 'elasticsearch', 'logstash', and 'kibana' data.
    """
    verify_ssl = elk_credentials.get("verify_ssl", True)
    session = requests.Session()
    session.verify = verify_ssl

    # Prepare final result
    elk_data = {
        "elasticsearch": None,
        "logstash": None,
        "kibana": None
    }

    # 1. Elasticsearch
    es_url = elk_credentials.get("elasticsearch_url")
    es_user = elk_credentials.get("es_username")
    es_pass = elk_credentials.get("es_password")
    if es_url and es_user and es_pass:
        session.auth = (es_user, es_pass)
        try:
            # a) Cluster health
            health_url = f"{es_url}/_cluster/health"
            h_resp = session.get(health_url)
            h_resp.raise_for_status()
            cluster_health = h_resp.json()

            # b) List some indices
            indices_url = f"{es_url}/_cat/indices?format=json&bytes=b"
            i_resp = session.get(indices_url)
            i_resp.raise_for_status()
            indices_info = i_resp.json()

            elk_data["elasticsearch"] = {
                "cluster_health": cluster_health,
                "indices": indices_info
            }
        except requests.RequestException as e:
            elk_data["elasticsearch"] = {"error": str(e)}

    # 2. Logstash
    logstash_url = elk_credentials.get("logstash_url")
    ls_user = elk_credentials.get("logstash_username")
    ls_pass = elk_credentials.get("logstash_password")
    if logstash_url and ls_user and ls_pass:
        session.auth = (ls_user, ls_pass)
        try:
            # Logstash pipelines info
            pipeline_url = f"{logstash_url}/_node/pipelines?pretty"
            p_resp = session.get(pipeline_url)
            p_resp.raise_for_status()
            pipelines_data = p_resp.json()

            elk_data["logstash"] = {
                "pipelines": pipelines_data
            }
        except requests.RequestException as e:
            elk_data["logstash"] = {"error": str(e)}

    # 3. Kibana
    kibana_url = elk_credentials.get("kibana_url")
    kb_user = elk_credentials.get("kibana_username")
    kb_pass = elk_credentials.get("kibana_password")
    if kibana_url and kb_user and kb_pass:
        session.auth = (kb_user, kb_pass)
        # Example: fetch saved objects
        # NB: Requires Kibana API to be properly accessible
        so_url = f"{kibana_url}/api/saved_objects/_find?type=dashboard&per_page=10"
        try:
            so_resp = session.get(so_url, headers={"kbn-xsrf": "true"})
            so_resp.raise_for_status()
            saved_objects = so_resp.json()

            elk_data["kibana"] = {
                "saved_dashboards": saved_objects
            }
        except requests.RequestException as e:
            elk_data["kibana"] = {"error": str(e)}

    return elk_data


def summarize_elk_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize ELK stack data using Gemini.

    :param credentials: Dict with optional "elasticsearch_url", "logstash_url",
                       "kibana_url" plus user/passwords, and "verify_ssl".
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Elasticsearch, Logstash, Kibana resources.
    """
    # 1. Fetch data
    elk_data = fetch_elk_data(credentials)

    # 2. Convert to JSON
    elk_data_str = json.dumps(elk_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert in the ELK stack (Elasticsearch, Logstash, Kibana). Summarize:\n"
        "• Elasticsearch cluster health, indices\n"
        "• Logstash pipelines\n"
        "• Kibana saved dashboards\n"
        "Highlight errors, potential performance issues, or anomalies."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, elk_data_str, prompt_instructions)
    return summary


###############################################################################
# 4. Datadog – Data Retrieval & Summarization
###############################################################################

def fetch_datadog_data(
    datadog_api_key: str,
    datadog_app_key: str,
    verify_ssl: bool = True,
    site: str = "datadoghq.com"
) -> Dict[str, Any]:
    """
    Fetch data from Datadog, such as monitors and dashboards.
    - Uses the v1 API endpoints for simplicity.

    :param datadog_api_key: Datadog API key.
    :param datadog_app_key: Datadog Application key.
    :param verify_ssl: Whether to verify SSL.
    :param site: Datadog site domain, default "datadoghq.com" (others: "datadoghq.eu", etc.)
    :return: A dictionary of Datadog resources (monitors, dashboards).
    """
    session = requests.Session()
    session.verify = verify_ssl

    base_url = f"https://api.{site}/api/v1"

    # 1. Monitors
    monitors_url = f"{base_url}/monitor?api_key={datadog_api_key}&application_key={datadog_app_key}"
    mon_resp = session.get(monitors_url)
    mon_resp.raise_for_status()
    monitors_data = mon_resp.json()

    # 2. Dashboards
    # This is the older v1 dashboards endpoint. For more advanced usage, see v2.
    dashboards_url = f"{base_url}/dashboard?api_key={datadog_api_key}&application_key={datadog_app_key}"
    dash_resp = session.get(dashboards_url)
    dash_resp.raise_for_status()
    dashboards_data = dash_resp.json()

    return {
        "monitors": monitors_data,
        "dashboards": dashboards_data
    }


def summarize_datadog_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Datadog data using Gemini.

    :param credentials: Dict with "datadog_api_key", "datadog_app_key", "verify_ssl", "site".
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Datadog monitors and dashboards.
    """
    # 1. Fetch data
    dd_data = fetch_datadog_data(
        datadog_api_key=credentials["datadog_api_key"],
        datadog_app_key=credentials["datadog_app_key"],
        verify_ssl=credentials.get("verify_ssl", True),
        site=credentials.get("site", "datadoghq.com")
    )

    # 2. Convert to JSON
    dd_data_str = json.dumps(dd_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert in Datadog monitoring. Summarize the following data with focus on:\n"
        "• Monitors (types, statuses, key metrics monitored)\n"
        "• Dashboards (content, usage)\n"
        "Highlight any frequent alerts, anomalies, or potential improvements."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, dd_data_str, prompt_instructions)
    return summary


###############################################################################
# 5. Example Main
###############################################################################

if __name__ == "__main__":
    # Prometheus Credentials Example
    prometheus_credentials = {
        "prometheus_url": "http://prometheus.example.com:9090",
        "auth_token": None,
        "verify_ssl": False
    }

    # Grafana Credentials Example
    grafana_credentials = {
        "grafana_url": "http://grafana.example.com",
        "api_token": "my-grafana-token",
        "verify_ssl": False
    }

    # ELK Credentials Example (some parts omitted for brevity)
    elk_credentials = {
        "elasticsearch_url": "http://es.example.com:9200",
        "es_username": "elastic",
        "es_password": "changeme",

        "logstash_url": "http://logstash.example.com:9600",
        "logstash_username": "logstashuser",
        "logstash_password": "logstashpass",

        "kibana_url": "http://kibana.example.com:5601",
        "kibana_username": "kibanauser",
        "kibana_password": "kibanapass",

        "verify_ssl": False
    }

    # Datadog Credentials Example
    datadog_credentials = {
        "datadog_api_key": "my-datadog-api-key",
        "datadog_app_key": "my-datadog-app-key",
        "verify_ssl": True,
        "site": "datadoghq.com"
    }

    # Replace with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    print("===== PROMETHEUS SUMMARY =====")
    prom_summary = summarize_prometheus_data(prometheus_credentials, GEMINI_API_KEY)
    print(prom_summary)
    print()

    print("===== GRAFANA SUMMARY =====")
    graf_summary = summarize_grafana_data(grafana_credentials, GEMINI_API_KEY)
    print(graf_summary)
    print()

    print("===== ELK SUMMARY =====")
    elk_summary = summarize_elk_data(elk_credentials, GEMINI_API_KEY)
    print(elk_summary)
    print()

    print("===== DATADOG SUMMARY =====")
    dd_summary = summarize_datadog_data(datadog_credentials, GEMINI_API_KEY)
    print(dd_summary)
