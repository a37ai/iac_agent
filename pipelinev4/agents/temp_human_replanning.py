from typing import TypedDict, List, Dict, Optional, Annotated, Literal
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
from pydantic import BaseModel
import json
import os
from pathlib import Path
from prompts import replanning_prompt
from states.state import PlanStep, EditRequest, ReplanningState, Plan
from utils.plan_manager import save_plan
from ai_models.openai_models import get_open_ai


def replan(state: ReplanningState) -> ReplanningState:
    """Create an updated plan based on the edit request."""
    llm = get_open_ai(temperature=0.3, model='gpt-4o')
    
    response = llm.with_structured_output(Plan).invoke(
        replanning_prompt.format(
            edit_request=json.dumps(state["edit_request"].dict(), indent=2),
            original_plan=json.dumps([step.dict() for step in state["plan"]], indent=2),
            codebase_overview=state["codebase_overview"],
            file_tree=state["file_tree"],
            file_analyses=json.dumps(state["file_analyses"], indent=2)
        )
    )
    
    state["plan"] = response.steps
    state["iteration"] += 1
    
    # Save the updated plan
    save_plan(state["plan"], state["repo_path"])
    
    # Add summary to messages
    state["messages"].append(
        HumanMessage(content=f"\n=== Plan Updated (Iteration {state['iteration']}) ===\n"
                            f"Edit request has been applied. Review the updated plan.")
    )
    
    return state

def get_edit_request_from_cli() -> EditRequest:
    """Get edit request details from CLI interaction."""
    print("\nWhat changes would you like to make to the plan?")
    print("(Type 'done' to finish replanning)")
    request = input("Enter your edit request: ").strip()
    
    if request.lower() == 'done':
        return None
        
    print("\nWould you like to provide a rationale for this edit? (optional, press Enter to skip)")
    rationale = input("Enter rationale: ").strip() or None
    
    return EditRequest(
        request=request,
        rationale=rationale
    )