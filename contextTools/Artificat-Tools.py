"""
Artifact Repositories – Data Retrieval & Summarization

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. Nexus:
   Provide a dictionary like:
       {
         "nexus_url": "https://nexus.example.com",
         "username": "admin",
         "password": "my-nexus-password",
         "verify_ssl": True
       }
   - This script uses Nexus REST APIs (e.g., /service/rest/v1/repositories) to list repositories
     and optionally sample some artifact info.

2. JFrog Artifactory:
   Provide a dictionary like:
       {
         "artifactory_url": "https://artifactory.example.com/artifactory",
         "api_key": "some-api-key-or-token",
         "verify_ssl": True
       }
   - This script queries Artifactory's REST APIs to list repositories, gather some artifact details,
     and optionally list permission targets.

3. Gemini LLM API Key:
   Provide your Gemini API key as a string, e.g.:
       GEMINI_API_KEY = "your-api-key"

--------------------------------------------------------------------------------
DEPENDENCIES:
   pip install requests
   pip install google-generativeai
--------------------------------------------------------------------------------
"""

import json
import os
import requests
from typing import Dict, Any

# For Google Generative AI (Gemini)
try:
    import google.generativeai as genai
except ImportError:
    print("WARNING: Gemini portion requires 'google-generativeai'. "
          "Install with: pip install google-generativeai")


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
# 1. Nexus – Data Retrieval & Summarization
###############################################################################

def fetch_nexus_data(
    nexus_url: str,
    username: str,
    password: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from a Sonatype Nexus server (version 3.x assumed).
    Typical data includes:
      - Repositories (type, format, online status)
      - Optionally, a sample of components from each repository (if feasible)

    :param nexus_url: Base URL of Nexus (e.g. "https://nexus.example.com").
    :param username: Nexus username (with read privileges).
    :param password: Nexus password or token.
    :param verify_ssl: Whether to verify SSL certs.
    :return: A dictionary of structured Nexus data.
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.auth = (username, password)

    result = {
        "repositories": [],
        "repo_components_sample": {},
        "errors": []
    }

    # 1) List repositories
    # Nexus 3 API: /service/rest/v1/repositories
    repos_endpoint = f"{nexus_url}/service/rest/v1/repositories"
    try:
        resp = session.get(repos_endpoint)
        resp.raise_for_status()
        repos_data = resp.json()

        # repos_data is a list of repos
        for repo in repos_data:
            repo_info = {
                "name": repo.get("name"),
                "format": repo.get("format"),
                "type": repo.get("type"),
                "url": repo.get("url"),
                "online": repo.get("online")
            }
            result["repositories"].append(repo_info)
    except requests.RequestException as e:
        result["errors"].append(f"Failed to list repositories: {str(e)}")
        return result

    # 2) Optionally fetch sample of components from each repository (if the Nexus format supports it)
    # For each repo, we can query /service/rest/v1/components?repository=<repoName>
    for repo in result["repositories"]:
        repo_name = repo["name"]
        comp_url = f"{nexus_url}/service/rest/v1/components?repository={repo_name}"
        try:
            resp_comp = session.get(comp_url)
            resp_comp.raise_for_status()
            comp_data = resp_comp.json()
            items = comp_data.get("items", [])
            # Just store the first 3 for brevity
            sample = items[:3]
            result["repo_components_sample"][repo_name] = sample
        except requests.RequestException as e:
            result["errors"].append(f"Failed to fetch components for {repo_name}: {str(e)}")

    return result


def summarize_nexus_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Nexus data using Gemini.

    :param credentials: Dict with 'nexus_url', 'username', 'password', 'verify_ssl'.
    :param api_key: Gemini API key.
    :param model_name: The Gemini model to use.
    :return: Summarized text of Nexus repositories and sample components.
    """
    nexus_data = fetch_nexus_data(
        nexus_url=credentials["nexus_url"],
        username=credentials["username"],
        password=credentials["password"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    nexus_data_str = json.dumps(nexus_data, indent=2)
    configure_llm(api_key)

    prompt_instructions = (
        "You are an expert in Sonatype Nexus artifact repositories. Summarize the following data:\n"
        "• Repositories (names, formats, online status)\n"
        "• Sample components from each repo\n"
        "• Any errors\n"
        "Highlight unusual configurations, potential issues, or best practices for artifact management."
    )

    summary = summarize_with_llm(model_name, nexus_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. Artifactory – Data Retrieval & Summarization
###############################################################################

def fetch_artifactory_data(
    artifactory_url: str,
    api_key: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from a JFrog Artifactory server. Typical data includes:
      - Repositories (key, type, packageType)
      - Optionally, sample artifacts or permission targets.

    :param artifactory_url: Base URL of Artifactory (e.g. "https://artifactory.example.com/artifactory").
    :param api_key: Artifactory API key or token.
    :param verify_ssl: Whether to verify SSL certs.
    :return: Dictionary of Artifactory data (repositories, sample info, etc.).
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.headers.update({"X-JFrog-Art-Api": api_key})

    result = {
        "repositories": [],
        "repo_artifacts_sample": {},
        "permission_targets": [],
        "errors": []
    }

    # 1) List repositories
    # Artifactory REST API: GET /api/repositories
    repos_endpoint = f"{artifactory_url}/api/repositories"
    try:
        resp = session.get(repos_endpoint)
        resp.raise_for_status()
        repos_data = resp.json()  # list of repos
        for repo in repos_data:
            repo_info = {
                "key": repo.get("key"),
                "rtype": repo.get("type"),
                "packageType": repo.get("packageType"),
                "url": repo.get("url"),
            }
            result["repositories"].append(repo_info)
    except requests.RequestException as e:
        result["errors"].append(f"Failed to list repositories: {str(e)}")
        return result

    # 2) Fetch sample artifacts for each repository (just an example, limited approach)
    #    We'll query /api/storage/<repoKey>?list&listFolders=0 for a small subset.
    for repo in result["repositories"]:
        repo_key = repo["key"]
        storage_endpoint = f"{artifactory_url}/api/storage/{repo_key}?list&listFolders=0"
        try:
            storage_resp = session.get(storage_endpoint)
            storage_resp.raise_for_status()
            storage_data = storage_resp.json()
            files_list = storage_data.get("files", [])
            # Just store up to 3
            result["repo_artifacts_sample"][repo_key] = files_list[:3]
        except requests.RequestException as e:
            result["errors"].append(f"Failed to fetch artifacts for {repo_key}: {str(e)}")

    # 3) Permission Targets
    # Artifactory REST API: GET /api/security/permissions
    perm_endpoint = f"{artifactory_url}/api/security/permissions"
    try:
        perm_resp = session.get(perm_endpoint)
        # Some older Artifactory versions might not have this endpoint or require special perms
        if perm_resp.ok:
            perm_data = perm_resp.json()
            result["permission_targets"] = perm_data.get("permissionTargets", perm_data)
        else:
            result["errors"].append(f"Permission targets not accessible. Status: {perm_resp.status_code}")
    except requests.RequestException as e:
        result["errors"].append(f"Failed to list permission targets: {str(e)}")

    return result


def summarize_artifactory_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Artifactory data using Gemini.

    :param credentials: Dict with 'artifactory_url', 'api_key', 'verify_ssl'.
    :param api_key: Gemini API key.
    :param model_name: Gemini model to use.
    :return: Summarized text of Artifactory repositories, artifacts, and permissions.
    """
    art_data = fetch_artifactory_data(
        artifactory_url=credentials["artifactory_url"],
        api_key=credentials["api_key"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    art_data_str = json.dumps(art_data, indent=2)
    configure_llm(api_key)

    prompt_instructions = (
        "You are an expert in JFrog Artifactory. Summarize the following data:\n"
        "• Repositories (keys, package types, URLs)\n"
        "• Sample artifacts from each repository\n"
        "• Permission targets (if available)\n"
        "• Any errors encountered\n"
        "Highlight security issues, potential misconfigurations, or best practices for artifact management."
    )

    summary = summarize_with_llm(model_name, art_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. Example Main
###############################################################################

if __name__ == "__main__":
    # Nexus Credentials Example
    nexus_credentials = {
        "nexus_url": "https://nexus.example.com",
        "username": "admin",
        "password": "my-nexus-password",
        "verify_ssl": True
    }

    # Artifactory Credentials Example
    artifactory_credentials = {
        "artifactory_url": "https://artifactory.example.com/artifactory",
        "api_key": "my-artifactory-api-key",
        "verify_ssl": True
    }

    # Replace with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    print("===== NEXUS SUMMARY =====")
    try:
        nexus_summary = summarize_nexus_data(nexus_credentials, GEMINI_API_KEY)
        print(nexus_summary)
    except Exception as e:
        print(f"Error summarizing Nexus: {e}")
    print()

    print("===== ARTIFACTORY SUMMARY =====")
    try:
        artifactory_summary = summarize_artifactory_data(artifactory_credentials, GEMINI_API_KEY)
        print(artifactory_summary)
    except Exception as e:
        print(f"Error summarizing Artifactory: {e}")
    print()
