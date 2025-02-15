from typing import Dict, List, Optional, Any, TypedDict, Literal, Annotated
from langgraph.graph import StateGraph, END
from states.state import MemoryState, DevOpsState, ReplanningState, AnalyzerState, PlanningState
from agents.agents import MemoryService
from agents.temp_devops import get_next_action, execute_tool, route_to_tool_or_end
from agents.temp_human_replanning import replan, get_edit_request_from_cli
from agents.temp_llm_analyzer import analyze_file, generate_overview
from agents.temp_planning_workflow import generate_questions, create_plan, validate_plan, determine_next
from utils.plan_manager import load_plan

def create_memory_graph():
    """Create the memory workflow."""
    workflow = StateGraph(MemoryState)
    
    # Add nodes
    workflow.add_node("extract_memories", MemoryService().extract_memories)
    workflow.add_node("store_memories", MemoryService().store_memories)
    
    # Set entry point
    workflow.set_entry_point("extract_memories")
    
    # Add edges
    workflow.add_edge("extract_memories", "store_memories")
    workflow.add_edge("store_memories", END)
    
    return workflow.compile()

def create_devops_workflow() -> StateGraph:
    """Create the DevOps workflow graph."""
    from langgraph.graph import StateGraph
    workflow = StateGraph(DevOpsState)
    
    # Add nodes
    workflow.add_node("get_next_action", get_next_action)
    workflow.add_node("execute_tool", execute_tool)
    
    # After get_next_action, route based on decision
    workflow.add_conditional_edges(
        "get_next_action",
        route_to_tool_or_end,
        {
            "execute_tool": "execute_tool",
            "next_step": "get_next_action",
            "end": END
        }
    )
    
    # After execute_tool, always go back to get_next_action
    workflow.add_edge("execute_tool", "get_next_action")
    
    # Set entry point
    workflow.set_entry_point("get_next_action")
    return workflow.compile()

def start_replanning(
    repo_path: str,
    codebase_overview: str,
    file_tree: str,
    file_analyses: Dict[str, str]
) -> Dict:
    """Start the replanning workflow."""
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

def create_analyzer_workflow():
    """Create the analyzer workflow"""
    workflow = StateGraph(AnalyzerState)
    
    # Add nodes for file analysis and overview generation
    workflow.add_node("analyze_file", analyze_file)
    workflow.add_node("generate_overview", generate_overview)
    
    # Set entry point
    workflow.set_entry_point("analyze_file")
    
    # Add edges
    workflow.add_edge("analyze_file", "generate_overview")
    workflow.add_edge("generate_overview", END)
    
    return workflow.compile()

def create_planning_workflow() -> StateGraph:
    """
    Compose the planning workflow with:
      1) generate_questions -> 2) create_plan -> 3) validate -> (loop or end)
    """
    workflow = StateGraph(PlanningState)
    
    workflow.add_node("generate_questions", generate_questions)
    workflow.add_node("create_plan", create_plan)
    workflow.add_node("validate", validate_plan)
    
    # Initial entry point: gather clarifications
    workflow.set_entry_point("generate_questions")
    
    # Simple flow
    workflow.add_edge("generate_questions", "create_plan")
    workflow.add_edge("create_plan", "validate")
    
    # Validation can route to generate_questions for clarifications, 
    # or create_plan again, or end if complete
    workflow.add_conditional_edges(
        "validate",
        determine_next,
        {
            "generate_questions": "generate_questions",
            "create_plan": "create_plan",
            "end": END
        }
    )
    
    return workflow.compile()
