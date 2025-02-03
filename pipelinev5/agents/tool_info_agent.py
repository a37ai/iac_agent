import json
from typing import Any, Dict, Optional
from termcolor import colored

import google.generativeai as genai
from langchain_core.messages import SystemMessage
from utils.all_stack_summary import get_configured_integrations
from states.state import AgentGraphState
from ai_models.openai_models import get_open_ai_json
from agent_tools.tool_info_agent_tool import integration_info, artifactory_tools, cicd_tools, cloud_tools, cm_tools, container_tools, networking_tools, observability_tools, orchestration_tools, all_tools
from prompts.tool_info_prompt import TOOL_INFO_PROMPT

def tool_info_agent(
    state: AgentGraphState,
    model = None,
    server = None
) -> AgentGraphState:
    """
    This agent uses an LLM to detect if the user's query mentions a known DevOps integration tool.
    If so, it calls our inline `integration_info` function to retrieve a summary from Supabase,
    then saves that summary in `state["integration_info"]`.
    """
    
    # Track agent responses
    if "tool_info_agent_response" not in state:
        state["tool_info_agent_response"] = []

    # Pull the user's query from state
    user_query = state.get("query", "").strip()

    configured = get_configured_integrations(state.get("project_id", ""))

    configured_artifactory = ""
    configured_cicd = ""
    configured_cloud = ""
    configured_cm = ""
    configured_container = ""
    configured_networking = ""
    configured_observability = ""
    configured_orchestration = ""

    for tool in configured:
        if tool in artifactory_tools:
            configured_artifactory += tool
        elif tool in cicd_tools:
            configured_cicd += tool
        elif tool in cloud_tools:
            configured_cloud += tool
        elif tool in cm_tools:
            configured_cm += tool
        elif tool in container_tools:
            configured_container += tool
        elif tool in networking_tools:
            configured_networking += tool
        elif tool in observability_tools:
            configured_observability += tool
        elif tool in orchestration_tools:
            configured_orchestration += tool

    artifactory_prompt = "Artifactory (this will provide information about the user's artifact management tools)- " + configured_artifactory if configured_artifactory != "" else ""
    cicd_prompt = "CI/CD (this will give information about the user's CI/CD pipeline)- " + configured_cicd if configured_cicd != "" else ""
    cloud_prompt = "Cloud (this will provide details about the user's cloud providers and platforms)- " + configured_cloud if configured_cloud != "" else ""
    cm_prompt = "Configuration Management (this will provide information about the user's configuration management tools)- " + configured_cm if configured_cm != "" else ""
    container_prompt = "Container (this will inform about the user's container runtime environments and tools)- " + configured_container if configured_container != "" else ""
    networking_prompt = "Network (this will give insights into the user's networking tools and services)- " + configured_networking if configured_networking != "" else ""
    observability_prompt = "Observability (this will provide information about the user's observability, monitoring, and logging systems)- " + configured_observability if configured_observability != "" else ""
    orchestration_prompt = "Orchestration (this will detail the user's container orchestration platforms and methodologies)- " + configured_orchestration if configured_orchestration != "" else ""

    # 1) Identify which tool (if any) is mentioned in the user query
    system_prompt = TOOL_INFO_PROMPT.format(
        artifactory_tools=artifactory_prompt,
        cicd_tools=cicd_prompt,
        cloud_tools=cloud_prompt,
        cm_tools=cm_prompt,
        container_tools=container_prompt,
        networking_tools=networking_prompt,
        observability_tools=observability_prompt,
        orchestration_tools=orchestration_prompt,
        query=user_query
    )
    print(system_prompt)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Identify the correct 'tool_name' from the user query."}
    ]

    llm = get_open_ai_json(model="gpt-4o-mini")


    llm_response = llm.invoke(messages)

    # Extract tool_name from JSON
    try:
        resp_data = json.loads(llm_response.content)
        tool_name = resp_data.get("tool_name", "none").lower().strip()
        reasoning = resp_data.get("reasoning", "")
        print(colored(f"\nTool Detection 🔍: Found '{tool_name}'", 'cyan'))
        print(colored(f"Reasoning: {reasoning}", 'blue'))
    except (json.JSONDecodeError, TypeError):
        tool_name = "none"
        reasoning = "Failed to parse tool name from LLM response."
        print(colored(f"Error parsing LLM response: {reasoning}", 'red'))

    # 2) If tool_name is known, retrieve the integration summary
    if tool_name in all_tools:
        print(colored(f"\nRetrieving integration info for {tool_name}...", 'yellow'))

        summary = integration_info(
            query=user_query,
            integration_name=tool_name,
            project_id=state.get("project_id")
        )
        print(colored(summary, 'yellow'))
        print(colored("Integration info retrieved successfully ✅", 'green'))
    else:
        summary = "No recognized integration found in the user query."
        print(colored(f"\n{summary}", 'yellow'))

    # Save the result in state
    state["integrations_info"] = summary

    # Build a final debug message to store in our agent's response
    final_message = (
        f"[Tool Info Agent Summary]\n"
        f"Detected Tool: {tool_name}\n"
        f"Reasoning: {reasoning}\n"
        f"Summary:\n{summary}"
    )
    print(colored("\n" + "="*50, "magenta"))
    print(colored(final_message, "magenta"))
    print(colored("="*50, "magenta"))
    
    # Append the SystemMessage for debugging or UI logs
    state["tool_info_agent_response"].append(SystemMessage(content=final_message))

    return state
