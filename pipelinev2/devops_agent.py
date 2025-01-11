"""Main DevOps agent implementation. Steps are ended when LLM says 'end'."""

from typing import Dict, List, Optional, Any, TypedDict, Literal, Annotated
from dataclasses import dataclass
from pathlib import Path
import json
import logging
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
import os
from prompts.devops_agent_prompt import DEVOPS_AGENT_PROMPT
from tools import DevOpsTools, ToolResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Global variable to store the execution log file path
EXECUTION_LOG_FILE = None

def initialize_logging(state: Dict[str, Any]) -> str:
    """Initialize logging for a new execution."""
    global EXECUTION_LOG_FILE
    
    log_dir = os.path.join(state["current_directory"], "logs", "devops_agent")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    EXECUTION_LOG_FILE = os.path.join(log_dir, f"execution_{timestamp}_full.log")
    
    # Write initial execution header
    with open(EXECUTION_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== DevOps Agent Execution Log ===\n")
        f.write(f"Started at: {datetime.now().isoformat()}\n")
        f.write(f"Working Directory: {state['current_directory']}\n")
        f.write(f"Total Steps: {len(state['plan_steps'])}\n\n")
        
        # Log initial plan
        f.write("=== Execution Plan ===\n")
        for i, step in enumerate(state['plan_steps'], 1):
            f.write(f"\nStep {i}:\n")
            f.write(f"Description: {step.description}\n")
            f.write(f"Type: {step.step_type}\n")
            f.write(f"Files: {', '.join(step.files)}\n")
        f.write("\n" + "="*80 + "\n\n")
    
    return EXECUTION_LOG_FILE

def log_interaction(state: Dict[str, Any], node_name: str, details: Dict):
    """Write logs to the global EXECUTION_LOG_FILE with better formatting."""
    global EXECUTION_LOG_FILE
    
    # Initialize logging if not already done
    if EXECUTION_LOG_FILE is None:
        initialize_logging(state)
    
    with open(EXECUTION_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Node: {node_name}\n")
        f.write(f"Step: {state['current_step_index'] + 1}/{len(state['plan_steps'])}\n")
        f.write(f"Attempt: {state['current_step_attempts']}\n")
        f.write(f"Total Attempts: {state['total_attempts']}\n\n")
        
        # Log step details
        if state['current_step_index'] < len(state['plan_steps']):
            current_step = state['plan_steps'][state['current_step_index']]
            f.write("Current Step Details:\n")
            f.write(f"Description: {current_step.description}\n")
            f.write(f"Type: {current_step.step_type}\n")
            f.write(f"Files: {', '.join(current_step.files)}\n\n")
        
        f.write("Action Details:\n")
        for key, value in details.items():
            f.write(f"{key}:\n")
            if isinstance(value, dict):
                f.write(json.dumps(value, indent=2) + "\n")
            elif isinstance(value, list):
                for item in value:
                    f.write(f"- {item}\n")
            else:
                f.write(f"{str(value)}\n")
            f.write("\n")
        
        # If we have knowledge_sequence, log a summary
        if state.get('knowledge_sequence'):
            f.write("\nKnowledge Sequence Summary:\n")
            f.write(f"Total Actions: {len(state['knowledge_sequence'])}\n")
            if state['knowledge_sequence']:
                last_action = state['knowledge_sequence'][-1]
                f.write("Last Action:\n")
                f.write(f"Type: {last_action.get('action_type', 'unknown')}\n")
                f.write(f"Status: {last_action.get('result', {}).get('status', 'unknown')}\n")
                if last_action.get('result', {}).get('error'):
                    f.write(f"Error: {last_action['result']['error']}\n")
        
        f.write("\n")

##############################################################################
#                               Data Models
##############################################################################

class PlanStep(BaseModel):
    description: str
    content: str
    step_type: str  # "code" or "command"
    files: List[str]

class LLMDecision(BaseModel):
    """Flattened LLM decision."""
    type: str
    description: str
    content: str
    reasoning: str

class DevOpsState(TypedDict):
    messages: Annotated[list, add_messages]
    plan_steps: List[PlanStep]
    current_step_index: int
    completed_steps: List[Dict[str, Any]]
    codebase_overview: str
    file_tree: str
    current_directory: str
    iam_permissions: Dict[str, Any]
    credentials: Dict[str, str]
    current_step_attempts: int
    current_step_context: Dict[str, Any]
    knowledge_sequence: List[Dict[str, Any]]
    total_attempts: int
    subprocess_handler: Any
    forge: Any
    tools: Optional[DevOpsTools]

##############################################################################
#                        Helper Formatting Functions
##############################################################################

def format_knowledge_sequence(knowledge_sequence: List[Dict], step_description: str) -> str:
    """Convert the knowledge_sequence (tool calls + outcomes) into text."""
    if not knowledge_sequence:
        return "No tool calls or outcomes for this step yet. This is the first time we're seeing this step."
    
    text = f"Current Step: {step_description}\n\n"
    for i, entry in enumerate(knowledge_sequence, 1):
        text += f"Action {i}:\n"
        text += f"Type: {entry['action_type']}\n"
        text += f"Input: {entry['action']}\n"
        text += f"Result: {entry['result']['status']}\n"
        if entry['result'].get('output'):
            shortened = entry['result']['output'][:200]
            text += f"Output: {shortened}...\n"
        if entry['result'].get('error'):
            text += f"Error: {entry['result']['error']}\n"
        text += "\n"
    return text

def format_completed_steps(completed_steps: List[Dict]) -> str:
    """Convert completed steps into text for LLM context."""
    if not completed_steps:
        return "No steps completed yet."
    
    text = "Completed Steps:\n"
    for i, s in enumerate(completed_steps, 1):
        text += f"Step {i}: {s['description']}\n"
        text += f"Status: {s['status']}\n"
        if 'summary' in s:
            text += f"Summary: {s['summary'].get('summary', 'No summary available')}\n"
        text += "\n"
    return text

##############################################################################
#                        Summarization for Step
##############################################################################

def format_step_knowledge(knowledge_sequence: List[Dict], step_description: str) -> str:
    """Convert the knowledge_sequence (tool calls + outcomes) into text."""
    if not knowledge_sequence:
        return "No execution history for this step."
    
    text = f"Current Step: {step_description}\n\n"
    for i, entry in enumerate(knowledge_sequence, 1):
        text += f"Action {i}:\n"
        text += f"Type: {entry['action_type']}\n"
        text += f"Input: {entry['action']}\n"
        text += f"Result: {entry['result']['status']}\n"
        if entry['result'].get('output'):
            shortened = entry['result']['output'][:200]
            text += f"Output: {shortened}...\n"
        if entry['result'].get('error'):
            text += f"Error: {entry['result']['error']}\n"
        text += "\n"
    return text

def summarize_step_knowledge(knowledge_sequence: List[Dict], step_description: str) -> Dict:
    """Use an LLM to summarize everything that happened in this step."""
    if not knowledge_sequence:
        return {
            "summary": "No actions taken",
            "key_learnings": [],
            "relevant_for_future": []
        }
    
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import PromptTemplate

    text_data = format_step_knowledge(knowledge_sequence, step_description)
    
    prompt = PromptTemplate(
        template="""You are analyzing the execution history of a step in a DevOps automation plan.
Execution History:
{step_data}

Provide a concise summary in this exact JSON format:
{{
  "summary": "Brief description of what was done",
  "key_learnings": ["List of key things learned"],
  "relevant_for_future": ["List of points relevant for future steps"]
}}""",
        input_variables=["step_data"]
    )
    
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        response = llm.invoke(prompt.format(step_data=text_data))
        
        # Try to parse JSON response
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON block
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                # If all parsing fails, return a default summary
                logger.warning(f"Failed to parse summary response: {response.content}")
                return {
                    "summary": "Step completed but summary generation failed",
                    "key_learnings": [],
                    "relevant_for_future": []
                }
    except Exception as e:
        logger.warning(f"Error summarizing step: {e}")
        return {
            "summary": "Step completed but summary generation failed",
            "key_learnings": [],
            "relevant_for_future": []
        }

##############################################################################
#                       Primary Flow Functions
##############################################################################

def get_next_action(state: DevOpsState) -> DevOpsState:
    """
    Query the LLM about what to do for the current step.
    If LLM says 'end', we end this step right away in the route function.
    """
    
    current_step = state["plan_steps"][state["current_step_index"]]

    print(f"Current step: {current_step}")
    # Potentially add files to forge context
    if current_step.files:
        for fpath in current_step.files:
            state["forge"].add_file(fpath)
    
    # Format context
    exec_history = format_knowledge_sequence(state["knowledge_sequence"], current_step.description)
    prev_steps = format_completed_steps(state["completed_steps"])
    current_step_json = json.dumps(current_step.dict(), indent=2)
    
    # Attempt to gather file contents
    file_contents = {}
    if state["forge"] and current_step.files:
        file_contents = state["forge"].get_file_contents()

    codebase_context = f"""Overview:
{state['codebase_overview']}

File Structure:
{state['file_tree']}

Relevant Files:
{json.dumps(file_contents, indent=2) if file_contents else 'No file contents available'}
"""
    
    context_for_llm = {
        "current_step": current_step_json,
        "previous_steps": prev_steps,
        "execution_history": exec_history,
        "codebase_context": codebase_context,
        "current_directory": state["current_directory"],
        "credentials": json.dumps(state["credentials"], indent=2)
    }
    
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import PromptTemplate

    prompt = PromptTemplate(
        template=DEVOPS_AGENT_PROMPT,
        input_variables=list(context_for_llm.keys())
    )
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
    try:
        decision = llm.with_structured_output(LLMDecision).invoke(
            prompt.format(**context_for_llm)
        )
        log_interaction(state, "get_next_action", {
            "context": context_for_llm,
            "decision": decision.dict(),
            "loaded_files": list(file_contents.keys()) if file_contents else []
        })
        
        state["current_step_context"]["last_decision"] = decision.dict()
        state["total_attempts"] += 1

        
        decision = LLMDecision(**decision.dict())
        
        # If LLM says "end" or "none", finalize current step
        if decision.type in ["end", "none"]:
            logger.info(f"LLM said '{decision.type}' => finalizing current step")
            
            # Summarize what was done so far
            step_summary = summarize_step_knowledge(
                state["knowledge_sequence"],
                state["plan_steps"][state["current_step_index"]].description
            )
            
            # Mark step as completed
            forced_step_info = {
                "description": state["plan_steps"][state["current_step_index"]].description,
                "status": "completed",
                "summary": step_summary,
                "result": {"status": "forced_end"},
                "tool_used": "none",
                "timestamp": datetime.now().isoformat()
            }
            state["completed_steps"].append(forced_step_info)
            
            # Move to the next step
            state["current_step_index"] += 1
            
            # Reset step state completely to ensure fresh context
            state["current_step_attempts"] = 0
            state["current_step_context"] = {}  # Clear last decision
            state["knowledge_sequence"] = []
            
            # If that was the last step, end workflow
            if state["current_step_index"] >= len(state["plan_steps"]):
                logger.info("No more steps remain after LLM ended the step.")
                return "end"


        return state
    except Exception as exc:
        logger.error(f"Error in get_next_action: {exc}")
        raise

def initialize_tools(state: DevOpsState) -> DevOpsTools:
    """Create a DevOpsTools instance if not present."""
    if not state.get("tools"):
        t = DevOpsTools(
            working_directory=state["current_directory"],
            subprocess_handler=state["subprocess_handler"]
        )
        t.set_forge(state["forge"])
        
        log_interaction(state, "tools_initialization", {
            "working_directory": state["current_directory"],
            "available_tools": [
                "execute_command",
                "execute_code",
                "retrieve_documentation"
                "ask_human",
                "run_file",
                "validate_output",
                "validate_code_changes",
                "validate_file_output",
                "delete_file",
                "create_file",
                "copy_template",
                "validate_command_output"
            ]
        })
        state["tools"] = t
    return state["tools"]

def execute_tool(state: DevOpsState) -> DevOpsState:
    """
    Execute a tool or do a code action, based on the LLM's last decision.
    If that decision is 'end', we do nothing here; route_to_tool_or_end handles forcibly marking step complete.
    """
    decision_data = state["current_step_context"]["last_decision"]
    decision = LLMDecision(**decision_data)
    
    # Log start
    log_interaction(state, "execute_tool_start", {
        "tool_type": decision.type,
        "description": decision.description,
        "content": decision.content,
        "reasoning": decision.reasoning
    })
    
        # Otherwise, run the selected tool
    tools = initialize_tools(state)
    tool_map = {
        "modify_code": "modify_code",
        "execute_command": "execute_command",
        "retrieve_documentation": "retrieve_documentation",
        "ask_human_for_information": "ask_human_for_information",
        "ask_human_for_intervention": "ask_human_for_intervention",
        "run_file": "run_file",
        "validate_output": "validate_output",
        "validate_code_changes": "validate_code_changes",
        "validate_file_output": "validate_file_output",
        "delete_file": "delete_file",
        "create_file": "create_file",
        "copy_template": "copy_template",
        "validate_command_output": "validate_command_output"
    }
    
    tool_func_name = tool_map.get(decision.type)
    if not tool_func_name:
        raise ValueError(f"Unknown action type {decision.type}")
    
    tool_func = getattr(tools, tool_func_name, None)
    if not tool_func:
        raise ValueError(f"Tools instance has no method {tool_func_name}")
    
    # Build tool inputs
    inputs = {}
    if decision.type == "modify_code":
        inputs["code"] = decision.content
        inputs["instructions"] = decision.description
    elif decision.type == "execute_command":
        inputs["command"] = decision.content
    elif decision.type == "retrieve_documentation":
        inputs["query"] = decision.content
    elif decision.type == "ask_human_for_information":
        inputs["question"] = decision.content
    elif decision.type == "ask_human_for_intervention":
        inputs["explanation"] = decision.content
    elif decision.type == "run_file":
        inputs["file_path"] = decision.content
    elif decision.type == "validate_output":
        inputs["output"] = decision.content
        inputs["expected_behavior"] = decision.description
        inputs["validation_criteria"] = []
    elif decision.type == "validate_code_changes":
        inputs["code"] = decision.content
        inputs["instructions"] = decision.description
        inputs["expected_changes"] = ""
    elif decision.type == "validate_file_output":
        inputs["file_content"] = decision.content
        inputs["expected_content"] = ""
    elif decision.type == "validate_command_output":
        inputs["command_output"] = decision.content
        inputs["expected_behavior"] = decision.description
    elif decision.type == "delete_file":
        inputs["file_path"] = decision.content
    elif decision.type == "create_file":
        inputs["file_path"] = decision.content
        inputs["content"] = ""
    elif decision.type == "copy_template":
        inputs["template_path"] = decision.content
    
    try:
        res = tool_func(**inputs)
        if not isinstance(res, ToolResult):
            raise ValueError(f"{tool_func_name} returned non-ToolResult: {type(res)}")
        
        knowledge_update = {
            "timestamp": datetime.now().isoformat(),
            "action_type": tool_func_name,
            "action": str(inputs),
            "result": res.dict(),
            "context": {
                "step_number": state["current_step_index"] + 1,
                "step_description": state["plan_steps"][state["current_step_index"]].description,
                "attempt_number": state["current_step_attempts"] + 1,
                "reasoning": decision.reasoning
            }
        }
        state["knowledge_sequence"].append(knowledge_update)
        
        log_interaction(state, "execute_tool_result", {
            "tool_result": res.dict(),
            "knowledge_update": knowledge_update
        })

        state["current_step_attempts"] += 1

    except Exception as ex:
        logger.error(f"Error executing tool {decision.type}: {ex}")
        log_interaction(state, "execute_tool_error", {
            "error": str(ex),
            "error_type": type(ex).__name__,
            "type": decision.type,
            "description": decision.description,
            "content": decision.content
        })
        state["current_step_attempts"] += 1
    
    return state

def route_to_tool_or_end(state: DevOpsState) -> Literal["execute_tool", "end", "next_step"]:
    """
    Decide if we are done or not. If LLM says 'end', forcibly finalize the current step and move to next.
    If no more steps, end entire workflow.
    """
    
    # Inspect the LLM's last decision

    if state["current_step_index"] >= len(state["plan_steps"]):
        logger.info("No more steps remain after LLM ended the step.")
        return "end"
    
    decision_data = state["current_step_context"].get("last_decision", {})

    if not decision_data:
        logger.info("No last decision. Ending workflow.")
        return "next_step"

    return "execute_tool"

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
    # This ensures we get fresh context for each step
    workflow.add_edge("execute_tool", "get_next_action")
    
    # Set entry point
    workflow.set_entry_point("get_next_action")
    return workflow.compile()

def start_devops_agent(
    plan_steps: List[PlanStep],
    repo_path: str,
    codebase_overview: str,
    file_tree: str,
    subprocess_handler: Any,
    forge: Any
) -> Dict[str, Any]:
    """Start the DevOps agent with forced finalization if the LLM says 'end'."""
    from langgraph.graph import END
    
    workflow = create_devops_workflow()
    
    initial_state = DevOpsState(
        messages=[],
        plan_steps=plan_steps,
        current_step_index=0,
        completed_steps=[],
        codebase_overview=codebase_overview,
        file_tree=file_tree,
        current_directory=str(Path(repo_path)),
        iam_permissions={},
        credentials={},
        current_step_attempts=0,
        current_step_context={},
        knowledge_sequence=[],
        total_attempts=0,
        subprocess_handler=subprocess_handler,
        forge=forge,
        tools=None
    )
    
    try:
        log_path = initialize_logging(initial_state)
        logger.info(f"Starting DevOps agent. Logs => {log_path}")
        
        final_state = workflow.invoke(initial_state)
        
        # Summarize
        with open(EXECUTION_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write("\n=== Execution Summary ===\n")
            f.write(f"Completed at: {datetime.now().isoformat()}\n")
            f.write(f"Total Steps Completed: {len(final_state['completed_steps'])}/{len(plan_steps)}\n")
            f.write(f"Total Attempts: {final_state['total_attempts']}\n\n")
            
            f.write("Completed Steps:\n")
            for i, step_info in enumerate(final_state["completed_steps"], 1):
                f.write(f"\nStep {i}:\n")
                f.write(f"Description: {step_info['description']}\n")
                f.write(f"Status: {step_info['status']}\n")
                if 'summary' in step_info:
                    f.write("Summary:\n")
                    f.write(json.dumps(step_info['summary'], indent=2) + "\n")
            
            f.write("\n=== End of Execution Log ===\n")
        
        logger.info("DevOps agent execution completed.")
        return {
            "completed_steps": final_state["completed_steps"],
            "total_attempts": final_state["total_attempts"],
            "knowledge_sequence": final_state["knowledge_sequence"],
            "log_file": log_path
        }
    except Exception as ex:
        logger.error(f"Error in devops agent: {ex}")
        if EXECUTION_LOG_FILE:
            with open(EXECUTION_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write("\n=== Execution Error ===\n")
                f.write(f"Error: {str(ex)}\n")
                f.write("=== End of Execution Log ===\n")
        raise
