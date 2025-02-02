import json
from typing import Dict
from states.state import AgentGraphState
from utils.general_helper_functions import configure_logger

logger = configure_logger(__name__)

def format_router_context(state: AgentGraphState) -> Dict[str, str]:
    """Format the context for the router agent's decision making with detailed execution history."""
    
    # Get current step if available
    current_step = None
    if state["current_step_index"] < len(state["plan_steps"]):
        current_step = state["plan_steps"][state["current_step_index"]]
    
    # Format execution history with full details
    exec_history = ""
    if state.get("knowledge_sequence"):
        for entry in state["knowledge_sequence"][-5:]:  # Last 5 entries
            exec_history += f"Action Type: {entry['action_type']}\n"
            
            # Include the actual action details
            if isinstance(entry['action'], str):
                try:
                    action_dict = eval(entry['action'])
                    if isinstance(action_dict, dict):
                        for key, value in action_dict.items():
                            exec_history += f"{key}: {value}\n"
                except:
                    exec_history += f"Action: {entry['action']}\n"
            
            # Include full result details
            exec_history += f"Result Status: {entry['result']['status']}\n"
            
            if entry['result'].get('output'):
                exec_history += f"Output:\n{entry['result']['output']}\n"
            
            if entry['result'].get('error'):
                exec_history += f"Error:\n{entry['result']['error']}\n"
            
            # Include context information
            if entry.get('context'):
                if entry['context'].get('reasoning'):
                    exec_history += f"Reasoning: {entry['context']['reasoning']}\n"
                if entry['context'].get('step_description'):
                    exec_history += f"Step Description: {entry['context']['step_description']}\n"
            
            exec_history += "\n"
    
    # Format retrieved documentation if available
    retrieved_docs = ""
    if state.get("retrieved_documentation"):
        retrieved_docs = "\n".join([
            f"Query: {doc['query']}\nInfo: {doc['info']}\n"
            for doc in state["retrieved_documentation"][-3:]  # Last 3 entries
        ])
    
    # Count errors and classify them
    error_entries = [e for e in state.get("knowledge_sequence", []) 
                    if e["result"]["status"] == "error"]
    error_count = len(error_entries)
    
    # Create error summary if there are errors
    error_summary = ""
    if error_entries:
        error_summary = "\nRecent Errors Summary:\n"
        for error in error_entries[-3:]:  # Last 3 errors
            error_summary += f"- Action: {error['action_type']}\n"
            error_summary += f"  Error: {error['result'].get('error', 'No error message')}\n"
    
    return {
        "current_step": json.dumps(current_step.dict()) if current_step else "No current step",
        "execution_history": exec_history or "No execution history",
        "retrieved_documentation": retrieved_docs or "No documentation retrieved yet",
        "error_count": error_count,
        "error_summary": error_summary,
        "current_step_attempts": state.get("current_step_attempts", 0)
    }