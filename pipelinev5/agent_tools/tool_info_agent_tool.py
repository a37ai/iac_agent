import json
from typing import Any, Dict, Optional
from termcolor import colored

import google.generativeai as genai
from langchain_core.messages import SystemMessage

from states.state import AgentGraphState
from pipelinev5.supabase import Supabase
from ai_models.openai_models import get_open_ai_json

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
    prompt_instructions: str
) -> str:
    """
    Send raw data and instructions to the specified Gemini model, returning a summary.
    """
    if not genai:
        raise ImportError("Gemini library not installed or not imported properly.")
    # Create a Gemini model instance
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
        response = supabase_client.get_integration_raw_data(integration_name, project_id)
        
        if not response or not response.data:
            return f"No data found in Supabase for '{integration_name}'."
        
        raw_data = response.data[0]
        if not raw_data:
            return f"Empty data for '{integration_name}' in Supabase."
        
        # Summarize using Gemini (or fallback if you wish to another model)
        try:
            summary = summarize_with_llm(
                model_name="models/gemini-1.5-pro", 
                raw_data=raw_data, 
                prompt_instructions=query
            )
            return summary
        except Exception as e:
            return f"Error summarizing data: {str(e)}"
    
    except Exception as e:
        return f"Supabase error retrieving integration data: {str(e)}"