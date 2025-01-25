from typing import Dict
import json
from termcolor import colored
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json
from states.state import AgentGraphState
from prompts.router_prompt import ROUTER_PROMPT

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