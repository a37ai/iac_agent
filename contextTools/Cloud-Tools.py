"""
AWS, Azure, GCP – Enhanced Data Retrieval & Summarization

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. AWS:
   Provide AWS credentials in a dictionary. Example:

   aws_credentials = {
       "aws_access_key_id": "AKIAxxx",
       "aws_secret_access_key": "xxxSECRETxxx",
       "aws_session_token": "xxxOPTIONALxxx",  # if STS tokens are used
       "region_name": "us-east-1",
       "role_arn": "arn:aws:iam::1234567890:role/MyRole"  # optional
   }

   - If 'role_arn' is provided, we attempt to assume that role using STS.
   - If it fails, we'll revert to the base credentials (if possible) or raise an error.
   - By default, we gather:
     • IAM role info (if role_arn is assumed)
     • EC2 instances across that region
     • S3 buckets globally

2. Azure:
   Provide a dictionary with a **service principal** for the subscription you want to inspect:

   azure_credentials = {
       "tenant_id": "xxxx-xxxx-xxxx-xxxx",
       "client_id": "yyyy-yyyy-yyyy-yyyy",
       "client_secret": "some-strong-secret",
       "subscription_id": "zzzz-zzzz-zzzz-zzzz"
   }

   By default, we gather:
     • Resource Groups (names, locations, tags)
     • Top-level resources across the subscription (type, location, group)

3. GCP:
   Provide a dictionary referencing your **service account JSON** and a specific project ID:

   gcp_credentials = {
       "service_account_json": "/path/to/my-service-account.json",
       "project_id": "my-gcp-project-id"
   }

   By default, we gather:
     • Project metadata (ID, name, state)
     • (Optional) If you enable additional code, you can list GCE instances or other resources.

4. Gemini LLM API Key:
   A valid Gemini API key to summarize the fetched cloud data.

--------------------------------------------------------------------------------
DEPENDENCIES:
   pip install boto3
   pip install azure-identity azure-mgmt-resource
   pip install google-auth google-cloud-resource-manager
   pip install google-generativeai
--------------------------------------------------------------------------------
"""

import json
import os
import sys
from typing import Dict, Any, Optional

# --- AWS Imports ---
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("WARNING: AWS portion requires 'boto3'. Install with: pip install boto3")
    boto3 = None

# --- Azure Imports ---
try:
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource import ResourceManagementClient
except ImportError:
    print("WARNING: Azure portion requires 'azure-identity' and 'azure-mgmt-resource'.")
    ClientSecretCredential = None

# --- GCP Imports ---
try:
    import google.auth
    from google.oauth2 import service_account
    from google.cloud import resourcemanager_v3
except ImportError:
    print("WARNING: GCP portion requires 'google-auth' and 'google-cloud-resource-manager'.")
    service_account = None

# --- Gemini Imports ---
try:
    import google.generativeai as genai
except ImportError:
    print("WARNING: Gemini portion requires 'google-generativeai'. Install with: pip install google-generativeai")
    genai = None


###############################################################################
# Utility: Configure Gemini & Summarization
###############################################################################

def configure_llm(api_key: str):
    """
    Configure the Google Generative AI client to use the specified API key.
    """
    if genai is None:
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
    if genai is None:
        raise ImportError("Gemini library not installed or not imported properly.")
    model = genai.GenerativeModel(model_name)
    prompt = f"{prompt_instructions}\n\n--- RAW DATA START ---\n{raw_data}\n--- RAW DATA END ---\n"
    response = model.generate_content(prompt)
    return response.text


###############################################################################
# 1. AWS – Data Retrieval & Summarization
###############################################################################

def build_aws_session(credentials: Dict[str, Any]):
    """
    Build a boto3 session from credentials. If 'role_arn' is provided, attempt
    to assume that role. If that fails, optionally fall back or raise error.

    :param credentials: Dict with AWS keys, region, optional role_arn.
    :return: A boto3.Session
    """
    if boto3 is None:
        raise ImportError("boto3 not installed or not imported properly.")

    base_session = boto3.Session(
        aws_access_key_id=credentials.get("aws_access_key_id"),
        aws_secret_access_key=credentials.get("aws_secret_access_key"),
        aws_session_token=credentials.get("aws_session_token"),
        region_name=credentials.get("region_name", "us-east-1"),
    )

    role_arn = credentials.get("role_arn")
    if role_arn:
        sts_client = base_session.client("sts")
        try:
            resp = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="AI_AgentSession"
            )
            creds = resp["Credentials"]
            assumed_session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=credentials.get("region_name", "us-east-1")
            )
            return assumed_session
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(f"Failed to assume role {role_arn}: {str(e)}")
    else:
        return base_session


def fetch_aws_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data from AWS:
      - If role_arn used, describe that IAM role
      - EC2 instance details
      - S3 buckets
    Return structured data, ignoring partial errors (but capturing them).

    :param credentials: AWS keys, region, optional role_arn.
    :return: A dictionary with AWS info. 
    """
    session = build_aws_session(credentials)
    data = {
        "assumed_role_summary": None,
        "ec2_instances": [],
        "s3_buckets": [],
        "errors": []
    }

    # If we used a role_arn, let's attempt to describe that role for context
    role_arn = credentials.get("role_arn")
    if role_arn:
        iam_client = session.client("iam")
        role_name = role_arn.split("/")[-1] if "/" in role_arn else role_arn
        try:
            resp = iam_client.get_role(RoleName=role_name)
            data["assumed_role_summary"] = {
                "arn": role_arn,
                "role_name": role_name,
                "description": resp["Role"].get("Description"),
                "creation_date": str(resp["Role"].get("CreateDate")),
                "assume_role_policy": resp["Role"].get("AssumeRolePolicyDocument"),
            }
        except ClientError as e:
            data["assumed_role_summary"] = {}
            data["errors"].append(f"IAM role fetch error: {str(e)}")

    # List EC2 instances
    try:
        ec2 = session.resource("ec2")
        for instance in ec2.instances.all():
            data["ec2_instances"].append({
                "id": instance.id,
                "instance_type": instance.instance_type,
                "state": instance.state["Name"],
                "launch_time": str(instance.launch_time),
                "tags": instance.tags
            })
    except (BotoCoreError, ClientError) as e:
        data["errors"].append(f"EC2 list error: {str(e)}")

    # List S3 buckets
    try:
        s3 = session.resource("s3")
        for bucket in s3.buckets.all():
            data["s3_buckets"].append({
                "name": bucket.name,
                "creation_date": str(bucket.creation_date)
            })
    except (BotoCoreError, ClientError) as e:
        data["errors"].append(f"S3 list error: {str(e)}")

    return data


def summarize_aws_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize AWS data using Gemini, highlighting IAM role details,
    EC2 instance states, and S3 buckets.

    :param credentials: AWS keys, region, optional role_arn.
    :param api_key: Gemini API key.
    :param model_name: Gemini model.
    :return: Summarized text of AWS data.
    """
    aws_data = fetch_aws_data(credentials)
    aws_data_str = json.dumps(aws_data, indent=2)

    configure_llm(api_key)
    prompt_instructions = (
        "You are an expert summarizer for AWS environments. Focus on:\n"
        "• The IAM Role (if assumed) - name, creation date, policy doc\n"
        "• EC2 instances (count, states, any interesting or unusual tags)\n"
        "• S3 buckets (naming, creation dates)\n"
        "• If there are errors, mention them.\n"
        "Highlight any security concerns, cost considerations, or best practices."
    )
    summary = summarize_with_llm(model_name, aws_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. Azure – Data Retrieval & Summarization
###############################################################################

def fetch_azure_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data from Azure, including:
      - Resource Groups
      - Resources within each group (limited to top-level or basic details)

    :param credentials: Dict with 'tenant_id', 'client_id', 'client_secret', 'subscription_id'.
    :return: A dictionary with resource groups, resources, and possible errors.
    """
    if ClientSecretCredential is None or ResourceManagementClient is None:
        raise ImportError("Azure libraries not installed properly.")

    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource import ResourceManagementClient

    data = {
        "resource_groups": [],
        "resources": [],
        "errors": []
    }

    tenant_id = credentials["tenant_id"]
    client_id = credentials["client_id"]
    client_secret = credentials["client_secret"]
    subscription_id = credentials["subscription_id"]

    try:
        azure_credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        resource_client = ResourceManagementClient(azure_credential, subscription_id)

        # List resource groups
        try:
            for rg in resource_client.resource_groups.list():
                data["resource_groups"].append({
                    "name": rg.name,
                    "location": rg.location,
                    "tags": rg.tags
                })
        except Exception as e:
            data["errors"].append(f"Resource group list error: {str(e)}")

        # List resources
        try:
            for res in resource_client.resources.list():
                # Resource ID structure: /subscriptions/1234/resourceGroups/rgName/providers/...
                # Let's do a quick parse
                rid_parts = res.id.split("/")
                rg_index = rid_parts.index("resourceGroups") + 1 if "resourceGroups" in rid_parts else None
                rg_name = rid_parts[rg_index] if rg_index else None

                data["resources"].append({
                    "name": res.name,
                    "type": res.type,
                    "location": res.location,
                    "resource_group": rg_name
                })
        except Exception as e:
            data["errors"].append(f"Resource list error: {str(e)}")

    except Exception as e:
        data["errors"].append(f"Azure credential or client initialization error: {str(e)}")

    return data


def summarize_azure_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Azure data using Gemini.

    :param credentials: Azure service principal + subscription details.
    :param api_key: Gemini API key.
    :param model_name: Gemini model name.
    :return: Summarized text of Azure data.
    """
    azure_data = fetch_azure_data(credentials)
    azure_data_str = json.dumps(azure_data, indent=2)

    configure_llm(api_key)
    prompt_instructions = (
        "You are an expert in Azure. Summarize the following data:\n"
        "• Resource Groups (names, locations)\n"
        "• Resources (type, location, group)\n"
        "• Mention any errors.\n"
        "Highlight unusual configurations, region distribution, cost considerations, or best practices."
    )
    summary = summarize_with_llm(model_name, azure_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. GCP – Data Retrieval & Summarization
###############################################################################

def fetch_gcp_data(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch data from GCP. By default, lists the specified project's metadata.

    Potential expansions:
      - Listing GCE instances, GKE clusters, etc. (requires additional scopes/APIs enabled).

    GCP credentials:
      {
        "service_account_json": "/path/to/service_account.json",
        "project_id": "my-gcp-project-id"
      }

    :return: Dictionary with project metadata, plus any errors.
    """
    if service_account is None or resourcemanager_v3 is None:
        raise ImportError("GCP libraries not installed properly.")

    import google.auth
    from google.oauth2 import service_account
    from google.cloud import resourcemanager_v3

    data = {
        "project_info": {},
        "errors": []
    }

    service_account_file = credentials.get("service_account_json")
    project_id = credentials.get("project_id")

    if not (service_account_file and project_id):
        raise ValueError("GCP credentials must include 'service_account_json' and 'project_id'")

    try:
        gcp_creds = service_account.Credentials.from_service_account_file(service_account_file)
        client = resourcemanager_v3.ProjectsClient(credentials=gcp_creds)

        project_name = f"projects/{project_id}"
        try:
            project = client.get_project(name=project_name)
            data["project_info"] = {
                "project_id": project.project_id,
                "name": project.display_name,
                "state": project.state.name if hasattr(project.state, "name") else str(project.state),
                "create_time": str(project.create_time),
            }
        except Exception as e:
            data["errors"].append(f"Project fetch error: {str(e)}")
    except Exception as e:
        data["errors"].append(f"GCP credential or client initialization error: {str(e)}")

    return data


def summarize_gcp_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize GCP project data using Gemini.

    :param credentials: Dict with 'service_account_json' and 'project_id'.
    :param api_key: Gemini API key.
    :param model_name: Gemini model.
    :return: Summarized text of GCP data (project info, etc.).
    """
    gcp_data = fetch_gcp_data(credentials)
    gcp_data_str = json.dumps(gcp_data, indent=2)

    configure_llm(api_key)
    prompt_instructions = (
        "You are an expert in Google Cloud Platform. Summarize the following:\n"
        "• Project ID, name, creation date, state\n"
        "• Any errors reported\n"
        "Highlight potential issues, e.g., suspended states, missing resources, or best practices."
    )
    summary = summarize_with_llm(model_name, gcp_data_str, prompt_instructions)
    return summary


###############################################################################
# 4. Example Main
###############################################################################

if __name__ == "__main__":
    # --------------
    # AWS Credentials Example
    # --------------
    aws_credentials = {
        "aws_access_key_id": "AKIAxxxxxxx",
        "aws_secret_access_key": "xxxxxxxxxxxxxx",
        # "aws_session_token": "..."  # optional if using STS sessions
        "region_name": "us-east-1",
        # "role_arn": "arn:aws:iam::1234567890:role/MyRole"  # optional
    }

    # --------------
    # Azure Credentials Example
    # --------------
    azure_credentials = {
        "tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "client_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
        "client_secret": "super-secret-key",
        "subscription_id": "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"
    }

    # --------------
    # GCP Credentials Example
    # --------------
    gcp_credentials = {
        "service_account_json": "/path/to/my-service-account.json",
        "project_id": "my-gcp-project-id"
    }

    # --------------
    # Gemini API Key
    # --------------
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    # --------------
    # Summaries
    # --------------
    print("===== AWS SUMMARY =====")
    try:
        aws_summary = summarize_aws_data(aws_credentials, GEMINI_API_KEY)
        print(aws_summary)
    except Exception as e:
        print(f"Error summarizing AWS: {e}")
    print()

    print("===== AZURE SUMMARY =====")
    try:
        azure_summary = summarize_azure_data(azure_credentials, GEMINI_API_KEY)
        print(azure_summary)
    except Exception as e:
        print(f"Error summarizing Azure: {e}")
    print()

    print("===== GCP SUMMARY =====")
    try:
        gcp_summary = summarize_gcp_data(gcp_credentials, GEMINI_API_KEY)
        print(gcp_summary)
    except Exception as e:
        print(f"Error summarizing GCP: {e}")
    print()
