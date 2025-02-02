import json
from termcolor import colored
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json
from states.state import AgentGraphState
from prompts.router_prompt import ROUTER_PROMPT, tools_router_prompt
from ai_models.openai_models import get_open_ai_json
from utils.general_helper_functions import configure_logger
from agent_tools.router_tools import format_router_context

logger = configure_logger(__name__)

def router_agent(state: AgentGraphState, model=None, server=None) -> AgentGraphState:
    """
    Router agent that determines whether GitHub information is needed before planning.
    """
    try:
        # Format the routing prompt
        prompt = ROUTER_PROMPT.format(
            owner=state.get("github_owner", ""),
            repo=state.get("github_repo", ""),
            query=state["query"]
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": state["query"]}
        ]

        # Get LLM decision
        if server == 'openai':
            llm = get_open_ai_json(model=model)
        
        ai_msg = llm.invoke(messages)
        decision = json.loads(ai_msg.content)
        
        # Store decision in state
        state["needs_github"] = decision.get("needs_github", False)
        state["github_focus"] = decision.get("github_focus", [])
        
        # Store response for logging
        if "router_agent_response" not in state:
            state["router_agent_response"] = []
        state["router_agent_response"].append(
            SystemMessage(content=json.dumps(decision))
        )
        
        # Log decision
        print(colored(f"\nRouter Agent 🔄: {'GitHub information needed' if state['needs_github'] else 'No GitHub information needed'}", 'cyan'))
        print(colored(f"Rationale: {decision.get('rationale', '')}", 'blue'))
        
        return state

    except Exception as e:
        error_msg = f"Error in router_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        if "router_agent_response" not in state:
            state["router_agent_response"] = []
        state["router_agent_response"].append(SystemMessage(content=error_msg))
        return state
    

def tools_router_agent(state: AgentGraphState, model=None, server=None, os=None) -> AgentGraphState:
    """
    Main router agent function that decides whether to proceed with DevOps actions
    or retrieve additional documentation.
    """
    try:
        # Ensure state has required fields with proper types
        if not isinstance(state.get("needs_documentation"), bool):
            state["needs_documentation"] = False
        
        if "retrieved_documentation" not in state:
            state["retrieved_documentation"] = []
            
        if "router_response" not in state:
            state["router_response"] = []

        # Debug: Print state at start
        print(colored("\nDebug - Tools Router - Initial state:", 'yellow'))
        print(colored(f"needs_documentation: {state['needs_documentation']}", 'yellow'))
        print(colored(f"documentation_query: {state.get('documentation_query')}", 'yellow'))
        print(colored(f"Total docs retrieved: {len(state['retrieved_documentation'])}", 'yellow'))

        # Format context
        context = format_router_context(state)
        
        # Format the prompt with context directly
        formatted_prompt = tools_router_prompt.format(
            current_step=context["current_step"],
            execution_history=context["execution_history"],
            retrieved_documentation=context["retrieved_documentation"],
            error_count=context["error_count"],
            current_step_attempts=context["current_step_attempts"],
            os=os
        )

        # Get model and make decision
        llm = get_open_ai_json(temperature=0.0, model=model)
        messages = [
            {"role": "system", "content": formatted_prompt},
            {"role": "user", "content": "Please make a routing decision based on the current context."}
        ]
        
        response = llm.invoke(messages)
        decision = json.loads(response.content)

        # Add response to state
        state["router_response"].append(SystemMessage(content=response.content))

        # Log decision
        print(colored(f"\nRouter Decision 🔄: {decision['route']}", 'cyan'))
        print(colored(f"Reasoning: {decision['reasoning']}", 'cyan'))

        # Update routing state
        if decision["route"] == "documentation":
            state["needs_documentation"] = True
            state["documentation_query"] = decision.get("doc_query", "").strip()
            
            print(colored("\nDebug - Setting documentation state:", 'yellow'))
            print(colored(f"Setting needs_documentation to: {state['needs_documentation']}", 'yellow'))
            print(colored(f"Setting documentation_query to: {state['documentation_query']}", 'yellow'))
            
            if not state["documentation_query"]:
                print(colored("Warning: Empty documentation query received from decision", 'red'))
        else:
            # Only update flags, keep retrieved docs
            state["needs_documentation"] = False
            state["documentation_query"] = None
            print(colored("\nDebug - Moving to DevOps execution", 'yellow'))

        # Verify final state
        print(colored("\nDebug - Final state in router:", 'yellow'))
        print(colored(f"needs_documentation: {state['needs_documentation']}", 'yellow'))
        print(colored(f"documentation_query: {state['documentation_query']}", 'yellow'))
        print(colored(f"Total docs retrieved: {len(state['retrieved_documentation'])}", 'yellow'))
        
        return state

    except Exception as e:
        error_msg = f"Error in tools_router_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        if "router_response" not in state:
            state["router_response"] = []
        state["router_response"].append(SystemMessage(content=error_msg))
        return state