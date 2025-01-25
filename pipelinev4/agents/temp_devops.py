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
from agent_tools.tools import DevOpsTools, ToolResult
from utils.general_helper_functions import configure_logger
from utils.logging_helper_functions import initialize_logging, log_interaction, log_status_update
from states.state import DevOpsState, PlanStep, LLMDecision
from prompts.devops_agent_prompt import DECISION_SUMMARY_PROMPT, STEP_SUMMARY_PROMPT
from ai_models.openai_models import get_open_ai

logger = configure_logger(__name__)

##############################################################################
#                           Summaries for Decision
##############################################################################

class DecisionSummaryModel(BaseModel):
    tagline: str
    summary: str

def generate_quick_summary_from_decision(decision: "LLMDecision") -> (str, str):
    """
    Generate a short tagline and summary from the LLM decision.
    Returns a tuple of (tagline, summary).
    """
    try:
        llm = get_open_ai(temperature=0.3, model='gpt-4o')

        # Escape any curly braces in the content and description
        safe_content = str(decision.content).replace("{", "{{").replace("}", "}}")
        safe_description = str(decision.description).replace("{", "{{").replace("}", "}}")
        safe_reasoning = str(decision.reasoning).replace("{", "{{").replace("}", "}}")

        prompt_text = DECISION_SUMMARY_PROMPT.format(
            decision_type=decision.type,
            description=safe_description,
            content=safe_content,
            reasoning=safe_reasoning
        )

        response = llm.invoke(prompt_text)
        try:
            # Clean the response content of any markdown formatting
            content = response.content.strip()
            # Remove markdown code block if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            content = content.strip()
            
            data = json.loads(content)
            # Validate it has tagline and summary
            validated = DecisionSummaryModel(**data)
            return validated.tagline, validated.summary
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse decision summary as JSON: {response.content}\nError: {e}")
            # Provide meaningful defaults instead of "No tagline/summary"
            if decision.type == "end":
                return "Mission Accomplished", "The current step has been completed successfully. Moving to next step."
            return (
                f"DevOps {decision.type.replace('_', ' ').title()} in Progress",
                f"Performing a {decision.type.replace('_', ' ')} operation. {safe_description}"
            )
    except Exception as e:
        logger.warning(f"Could not generate quick summary: {str(e)}")
        return (
            f"DevOps {decision.type.replace('_', ' ').title()} in Progress",
            f"Performing a {decision.type.replace('_', ' ')} operation. {safe_description}"
        )

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
    

    text_data = format_step_knowledge(knowledge_sequence, step_description)
    
    prompt = PromptTemplate(
        template=STEP_SUMMARY_PROMPT,
        input_variables=["step_data"]
    )
    
    try:
        llm = get_open_ai(temperature=0.1, model='gpt-4o')
        response = llm.invoke(prompt.format(step_data=text_data))
        
        # Try to parse JSON response
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                return json.loads(json_match.group(0))
            else:
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
    Additionally, log a short summary (tagline + summary) of the LLM decision.
    """
    
    # Check if we're out of steps first
    if state["current_step_index"] >= len(state["plan_steps"]):
        # Instead of returning "end", we return the state and let route_to_tool_or_end handle it
        return state
    
    current_step = state["plan_steps"][state["current_step_index"]]

    print(f"Current step: {current_step}")
    # Potentially add files to forge context
    if current_step.files:
        for fpath in current_step.files:
            try:
                state["forge"].add_file(fpath)
            except Exception as e:
                logger.warning(f"File access error for {fpath}: {e}")
    
    # Format context
    exec_history = format_knowledge_sequence(state["knowledge_sequence"], current_step.description)
    prev_steps = format_completed_steps(state["completed_steps"])
    current_step_json = json.dumps(current_step.dict(), indent=2)
    
    # Attempt to gather file contents
    file_contents = {}
    if state["forge"] and current_step.files:
        try:
            file_contents = state["forge"].get_file_contents()
        except Exception as e:
            logger.warning(f"Could not retrieve file contents: {e}")

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
    
    prompt = PromptTemplate(
        template=DEVOPS_AGENT_PROMPT,
        input_variables=list(context_for_llm.keys())
    )
    llm = get_open_ai(temperature=0.1, model='gpt-4o')
    
    try:
        # 1) Get the LLM decision
        decision = llm.with_structured_output(LLMDecision).invoke(
            prompt.format(**context_for_llm)
        )
        # 2) Log the raw decision in the full log
        log_interaction(state, "get_next_action", {
            "context": context_for_llm,
            "decision": decision.dict(),
            "loaded_files": list(file_contents.keys()) if file_contents else []
        })
        
        state["current_step_context"]["last_decision"] = decision.dict()
        state["total_attempts"] += 1

        # 3) Generate a short summary from that decision and log it to the status log
        tagline, short_summary = generate_quick_summary_from_decision(decision)
        log_status_update(tagline, short_summary)

        decision = LLMDecision(**decision.dict())
        
        # 4) If LLM says "end" or "none", finalize current step
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
            state["current_step_context"] = {}
            state["knowledge_sequence"] = []

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
    
    # First check if we've completed all steps
    if state["current_step_index"] >= len(state["plan_steps"]):
        logger.info("No more steps remain. Ending workflow.")
        return "end"
    
    # Inspect the LLM's last decision
    decision_data = state["current_step_context"].get("last_decision", {})

    if not decision_data:
        logger.info("No last decision. Moving to next step.")
        return "next_step"
    
    # Continue with tool execution
    return "execute_tool"