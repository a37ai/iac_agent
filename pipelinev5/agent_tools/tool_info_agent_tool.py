import json
from typing import Any, Dict, Optional
from termcolor import colored

import google.generativeai as genai
from langchain_core.messages import SystemMessage

from states.state import AgentGraphState

from ai_models.openai_models import get_open_ai_json

import os
from supabase import create_client, Client
import traceback

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
        try:
            integration_column = f"{integration_name}_raw"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            response = response.data[0][integration_column]
            if not response:
                print(f"Failed to retrieve {integration_name} data")
                return None
                
            return str(response)
            
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
        try:
            integration_column = f"{integration_name}_summary"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            response = response.data[0][integration_column]
            if not response:
                print(f"No {integration_name} summary")
                return None
            
            return str(response)
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")

# -------------------------------------------------------------------------
# 1. Known DevOps tools list (moved from devops_tools.py)
# -------------------------------------------------------------------------
artifactory_tools = ["artifactory", "nexus"]
cicd_tools = ["jenkins", "github", "gitlab", "circleci"]
cloud_tools = ["aws", "azure", "gcp"]
cm_tools = ["ansible", "chef", "puppet"]
container_tools = ["docker", "podman"]
networking_tools = ["istio", "consul"]
observability_tools = ["datadog", "new_relic", "splunk", "elasticsearch", "grafana", "prometheus"]
orchestration_tools = ["kubernetes", "docker_swarm"]

all_tools = (
    artifactory_tools 
    + cicd_tools
    + cloud_tools
    + cm_tools
    + container_tools
    + networking_tools
    + observability_tools
    + orchestration_tools
)

# -------------------------------------------------------------------------
# 2. Utility function to summarize raw data with Gemini
# -------------------------------------------------------------------------
def summarize_with_llm(
    model_name: str,
    raw_data: str,
    prompt_instructions: str,
    api_key: str
) -> str:
    """
    Send raw data and instructions to the specified Gemini model, returning a summary.
    """
    if not genai:
        raise ImportError("Gemini library not installed or not imported properly.")
    # Create a Gemini model instance
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    # Build the prompt
    prompt = (
        f"{prompt_instructions}\n\n"
        "--- RAW DATA START ---\n"
        f"{raw_data}\n"
        "--- RAW DATA END ---\n"
    )
    
    # Generate the summary
    response = model.generate_content(prompt)
    return response.text

# -------------------------------------------------------------------------
# 3. Inline function to retrieve + summarize integration data from Supabase
# -------------------------------------------------------------------------
def integration_info(
    query: str,
    integration_name: str,
    project_id: Optional[str] = None
) -> str:
    """
    Retrieve and summarize information about the user's chosen integration.
    Calls Supabase to get the raw data for `integration_name`, then uses Gemini
    to summarize it with `query` as context instructions.
    """
    # Make sure integration_name is known
    if integration_name not in all_tools:
        return f"Integration '{integration_name}' not found in the known tools list."
    
    try:
        # Initialize Supabase client
        supabase_client = Supabase()
        
        # Retrieve raw data for the chosen integration
        raw_data = supabase_client.get_integration_raw_data(integration_name, project_id)
        
        if not raw_data or raw_data == "":
            return f"No data found in Supabase for '{integration_name}'."
        
        if not raw_data:
            return f"Empty data for '{integration_name}' in Supabase."
        
        # Summarize using Gemini (or fallback if you wish to another model)
        try:
            summary = summarize_with_llm(
                model_name="models/gemini-1.5-pro", 
                raw_data=raw_data, 
                prompt_instructions=query,
                api_key=os.getenv("GOOGLE_API_KEY")
            )
            return summary
        except Exception as e:
            return f"Error summarizing data: {str(e)}"
    
    except Exception as e:
        return f"Supabase error retrieving integration data: {str(e)}"
    
# print(integration_info("what cluster is prometheus running on", "prometheus", "89f1b2c5-c78b-426e-9567-62c8cac1c61e"))