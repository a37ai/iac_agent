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

class PlanStep(BaseModel):
    description: str
    content: str
    step_type: Literal["code", "command"]
    files: List[str] = []

class Plan(BaseModel):
    steps: List[PlanStep]

class EditRequest(BaseModel):
    """Structure for edit requests from users"""
    request: str
    rationale: Optional[str] = None

class ReplanningState(TypedDict):
    messages: Annotated[list, add_messages]
    edit_request: EditRequest
    repo_path: str
    codebase_overview: str
    file_tree: str
    file_analyses: Dict[str, str]
    plan: List[PlanStep]
    iteration: int

def replan(state: ReplanningState) -> ReplanningState:
    """Create an updated plan based on the edit request."""
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
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
    from plan_manager import save_plan
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

def start_replanning(
    repo_path: str,
    codebase_overview: str,
    file_tree: str,
    file_analyses: Dict[str, str]
) -> Dict:
    """Start the replanning workflow."""
    from plan_manager import load_plan
    iteration = 1
    
    while True:
        # Get edit request from user
        edit_request = get_edit_request_from_cli()
        if edit_request is None:
            break
            
        # Load the most recent plan before each iteration
        plan_steps = load_plan(repo_path)
        
        # Create initial state
        initial_state = ReplanningState(
            messages=[],
            repo_path=repo_path,
            codebase_overview=codebase_overview,
            file_tree=file_tree,
            file_analyses=file_analyses,
            plan=plan_steps,
            edit_request=edit_request,
            iteration=iteration
        )
        
        # Run workflow
        workflow = StateGraph(ReplanningState)
        workflow.add_node("replan", replan)
        workflow.set_entry_point("replan")
        workflow.add_edge("replan", END)
        
        final_state = workflow.compile().invoke(initial_state)
        iteration += 1
        
        print(f"\nIteration {iteration-1} complete. You can now review and modify the plan directly if needed.")
        print("When ready, you can enter another edit request or type 'done' to finish.")
    
    # Load the final plan state
    final_plan = load_plan(repo_path)
    return {"plan": [step.dict() for step in final_plan]} 