import json
import os
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from langchain_core.messages import SystemMessage, HumanMessage

from agents.planning_workflow_agents import question_generator_agent, plan_creator_agent, plan_validator_agent, end_node
# from agents.temp_devops import devops_agent, get_next_devops_action, execute_tool
from agents.devops_agents import get_next_devops_action, execute_tool

from agents.human_replanning_agents import replanning_agent
from agents.system_mapper_agents import system_mapper_agent
from agents.router_agents import router_agent
from agents.github_agents import github_agent
from agents.memory_agents import memory_agent
from agents.compression_agents import compression_agent

from prompts.planning_prompts import (
    question_generator_prompt_template,
    planning_prompt_template,
    validation_prompt_template,
)

from prompts.devops_agent_prompts import devops_prompt_template
from prompts.replanning_prompts import replanning_prompt_template


from states.state import AgentGraphState, get_agent_graph_state, state
from utils.plan_manager import load_plan
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

def create_graph(server=None, model=None, deepseek_model=None, stop=None, model_endpoint=None, 
                query=None, codebase_info=None, repo_path=None):
    """
    Create the full workflow graph combining planning, replanning, and devops execution.
    """
    graph = StateGraph(AgentGraphState)

    graph.add_node(
        "memory",
        lambda state: memory_agent(state)
    )

    graph.add_node(
        "system_mapper",
        lambda state: system_mapper_agent(state)
    )
    graph.add_node(
        "router",
        lambda state: router_agent(
            state=state,
            model=model,
            server=server
        )
    )

    graph.add_node(
        "github_agent",
        lambda state: github_agent(
            state=state,
            model=model,
            server=server
        )
    )

    # Planning nodes
    graph.add_node(
        "question_generator",
        lambda state: question_generator_agent(
            state=state,
            prompt=question_generator_prompt_template,
            feedback=lambda: state,
            model=model,
            server=server
        )
    )

    graph.add_node(
        "compression",
        lambda state: compression_agent(
            state=state,
            model=model,
            deepseek_model=deepseek_model,
            server=server
        )
    )

    graph.add_node(
        "plan_creator",
        lambda state: plan_creator_agent(
            state=state,
            prompt=planning_prompt_template,
            feedback=lambda: state,
            model=model,
            server=server
        )
    )

    graph.add_node(
        "plan_validator",
        lambda state: plan_validator_agent(
            state=state,
            prompt=validation_prompt_template,
            feedback=lambda: state,
            model=model,
            server=server
        )
    )

    # Replanning node
    graph.add_node(
        "replanning",
        lambda state: replanning_agent(
            state=state,
            prompt=replanning_prompt_template,
            feedback=lambda: state,
            model=model,
            server=server
        )
    )

    # DevOps execution node
    graph.add_node(
        "get_devops_action",
        lambda state: get_next_devops_action(
            state=state,
            prompt=devops_prompt_template,
            model=model,
            server=server
        )
    )
    
    # DevOps execution node
    graph.add_node(
        "execute_tool",
        lambda state: execute_tool(state)
    )

    # End node
    graph.add_node("end", lambda state: end_node(state=state))

    # Set entry point
    graph.set_entry_point("memory")
    
    # Set finish point
    graph.set_finish_point("end")

    graph.add_edge("memory", "system_mapper")
    graph.add_edge("system_mapper", "router")
    graph.add_edge("github_agent", "question_generator")
    graph.add_edge("question_generator", "compression")
    graph.add_edge("compression", "plan_creator")
    graph.add_edge("plan_creator", "plan_validator")
    graph.add_edge("execute_tool", "get_devops_action")

    # Conditional edges for router
    graph.add_conditional_edges(
        "router",
        lambda state: (
            "github_agent" 
            if state.get("needs_github", False)
            else "question_generator"
        )
    )

    # Conditional edges for plan validation
    graph.add_conditional_edges(
        "plan_validator",
        lambda state: (
            "question_generator" 
            if state["validation_result"] and state["validation_result"].status == "needs_info"
            else "plan_creator" 
            if state["validation_result"] and state["validation_result"].status == "has_issues"
            else "replanning"
        )
    )

    # Conditional edges for replanning
    graph.add_conditional_edges(
        "replanning",
        lambda state: (
            "plan_validator"
            if state.get("edit_request") and state.get("edit_request").get("request") != "done"
            else "get_devops_action"
        )
    )

    # Conditional edges for devops execution
    graph.add_conditional_edges(
        "get_devops_action",
        lambda state: (
            "end" 
            if state["current_step_index"] >= len(state["plan_steps"])
            else "execute_tool"
        )
    )

    return graph

def initialize_state(query: str, repo_path: str) -> AgentGraphState:
    """Initialize the state with required information."""
    initial_state = state.copy()
    
    # Get REPO_URLS from environment
    repo_url = os.getenv('REPO_URLS', '').strip()
    
    # Parse GitHub owner and repo from URL if present
    if repo_url and 'github.com' in repo_url:
        # Remove .git if present
        repo_url = repo_url.rstrip('.git')
        # Split URL into parts
        parts = repo_url.split('/')
        # Get owner and repo from parts
        if len(parts) >= 2:
            github_owner = parts[-2]
            github_repo = parts[-1]
        else:
            github_owner = None
            github_repo = None
    else:
        github_owner = None
        github_repo = None

    initial_state.update({
        "query": query,
        "repo_path": repo_path,
        "current_directory": str(repo_path),
        "plan_steps": [],
        "current_step_index": 0,
        "completed_steps": [],
        "knowledge_sequence": [],
        "iteration": 0,
        # Add GitHub-specific information
        "github_owner": github_owner,
        "github_repo": github_repo,
        "github_info": None,
        "needs_github": False,
        "github_focus": []
    })
    return initial_state

def compile_workflow(graph):
    """Compile the workflow graph."""
    return graph.compile()