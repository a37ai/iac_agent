import json
from termcolor import colored
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json
from states.state import AgentGraphState
from prompts.replanning_prompts import replanning_prompt_template
from utils.general_helper_functions import check_for_content
from agent_tools.human_replanning_tools import get_edit_request_from_cli

def replanning_agent(state: AgentGraphState, prompt=replanning_prompt_template, model=None, server=None, feedback=None, os=None):
    """Create an updated plan based on the edit request."""
    feedback_value = feedback() if callable(feedback) else feedback
    feedback_value = check_for_content(feedback_value)

    try:
        # Get the current plan and edit request from state
        print(colored("\nCurrent Plan:", 'cyan'))
        for i, step in enumerate(state["plan"], 1):
            print(colored(f"\nStep {i}:", 'green'))
            print(f"Description: {step.description}")  # Access as object attribute
            print(f"Type: {step.step_type}")         # Access as object attribute

        # Get edit request from user
        edit_request = get_edit_request_from_cli()
        if edit_request is None:
            state["edit_request"] = {"request": "done"}
            return state

        state["edit_request"] = edit_request.dict()
        
        # Convert plan steps to dictionaries for JSON serialization
        current_plan = [step.dict() for step in state.get("plan", [])]
        
        # Format the replanning prompt
        replanning_prompt = prompt.format(
            edit_request=json.dumps(edit_request.dict(), indent=2),
            original_plan=json.dumps(current_plan, indent=2),
            codebase_overview=state.get("codebase_overview", ""),
            file_tree=state.get("file_tree", ""),
            file_analyses=json.dumps(state.get("file_analyses", {}), indent=2),
            os=os
        )

        messages = [
            {"role": "system", "content": replanning_prompt},
            {"role": "user", "content": "Generate an updated plan based on the edit request"}
        ]

        if server == 'openai':
            llm = get_open_ai_json(model=model)
        
        ai_msg = llm.invoke(messages)
        response = ai_msg.content

        # Update state with the new plan and increment iteration
        if "replanning_response" not in state:
            state["replanning_response"] = []
        state["replanning_response"].append(SystemMessage(content=response))
        state["iteration"] = state.get("iteration", 0) + 1

        print(colored(f"Replanning Agent 🔄: Generated new plan (Iteration {state['iteration']})", 'green'))
        print(colored(f"Response: {response}", 'cyan'))

        return state

    except Exception as e:
        error_msg = f"Error in replanning_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        if "replanning_response" not in state:
            state["replanning_response"] = []
        state["replanning_response"].append(SystemMessage(content=error_msg))
        return state