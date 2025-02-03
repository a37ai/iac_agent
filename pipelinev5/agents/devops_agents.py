import json
from typing import Dict
from termcolor import colored
from datetime import datetime
from pathlib import Path
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json, get_open_ai_json_v2
from ai_models.deepseek_models import get_deepseek_groq_json
from states.state import AgentGraphState, LLMDecision, ToolResult
from utils.logging_helper_functions import log_interaction, log_status_update
from prompts.devops_agent_prompts import devops_prompt_template
from agent_tools.devops_tools import (
    format_knowledge_sequence,
    format_completed_steps,
    summarize_step_knowledge,
    generate_quick_summary_from_decision,
    DevOpsTools
)
from agent_tools.tool_info_agent_tool import Supabase

def get_next_devops_action(state: AgentGraphState, prompt=devops_prompt_template, model=None, server=None, feedback=None, os=None) -> AgentGraphState:
    """
    Determine the next action for the current step in the DevOps workflow.
    This function handles decision-making only, with execution handled separately.
    """
    try:
        # Initialize response list if not present
        if "devops_agent_response" not in state:
            state["devops_agent_response"] = []

        # Check if we're out of steps
        if state["current_step_index"] >= len(state["plan_steps"]):
            print(colored("DevOps Agent 🤖: No more steps remaining", 'yellow'))
            return state

        # Get current step and print status
        current_step = state["plan_steps"][state["current_step_index"]]
        print(colored(f"\nDevOps Agent 🤖: Processing step {state['current_step_index'] + 1}", 'cyan'))
        print(colored(f"Description: {current_step.description}", 'blue'))

        # Handle file context for Forge
        if current_step.files and state.get("forge"):
            for fpath in current_step.files:
                try:
                    state["forge"].add_file(fpath)
                    print(f"Files in chat context: {current_step.files}")
                except Exception as e:
                    print(colored(f"Warning: File access error for {fpath}: {e}", 'yellow'))

        # Get execution history and previous steps
        exec_history = format_knowledge_sequence(
            state["knowledge_sequence"],
            current_step.description
        )
        prev_steps = format_completed_steps(state["completed_steps"])
        
        # Get file contents if available
        file_contents = {}
        if state.get("forge") and current_step.files:
            try:
                file_contents = state["forge"].get_file_contents()
            except Exception as e:
                print(colored(f"Warning: Could not retrieve file contents: {e}", 'yellow'))

        # Format the context into the system prompt
        context_dict = {
            "current_step": json.dumps(current_step.dict(), indent=2),
            "previous_steps": prev_steps,
            "execution_history": exec_history,
            "codebase_context": _format_codebase_context(
                state["codebase_overview"],
                state["file_tree"],
                file_contents
            ),
            "current_directory": state["current_directory"],
            "credentials": json.dumps(state.get("credentials", {}), indent=2),
            # Add retrieved documentation directly in the context
            "retrieved_documentation": "\n".join(
                f"Query: {doc['query']}\nInformation:\n{doc['info']}\n"
                for doc in state.get("retrieved_documentation", [])
            ) or "No relevant documentation retrieved.",
            "os": os,
            "configured_integrations": Supabase.get_configured_integrations(state["project_id"]),
        }
        
        # Create the full system prompt by formatting the template with the context
        system_prompt = prompt.format(**context_dict)
        # print(f"DevOps Agent Prompt: {system_prompt}")

        # Prepare messages for LLM with simplified user message
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please decide what to do next based on the current context."}
        ]

        # Get LLM decision
        if server == 'openai':
            # llm = get_open_ai_json(model=model)
            # llm = get_open_ai_json_v2()
            llm = get_deepseek_groq_json()
        
        ai_msg = llm.invoke(messages)
        response = ai_msg.content

        response_data = json.loads(response)
        
        # Handle case where content might be a dictionary
        if isinstance(response_data.get('content'), dict):
            response_data['content'] = json.dumps(response_data['content'])
            
        decision = LLMDecision(**json.loads(response))
        
        # Generate and log summary
        tagline, summary = generate_quick_summary_from_decision(decision)
        log_status_update(tagline, summary)
        
        # Print decision details
        print(colored(f"DevOps Agent Decision 🤔: {decision.type}", 'magenta'))
        print(colored(f"Reasoning: {decision.reasoning}", 'cyan'))

        # Handle end/none decision types
        if decision.type in ["end", "none"]:
            print(colored(f"DevOps Agent 🤖: Step complete ({decision.type})", 'green'))
            
            # Create step summary
            step_summary = summarize_step_knowledge(
                state["knowledge_sequence"],
                current_step.description
            )
            
            # Record completion
            completed_step = {
                "description": current_step.description,
                "status": "completed",
                "summary": step_summary,
                "result": {"status": "success"},
                "tool_used": "none",
                "timestamp": datetime.now().isoformat()
            }
            state["completed_steps"].append(completed_step)
            
            # Reset step state
            state["current_step_attempts"] = 0
            state["knowledge_sequence"] = []
            state["current_step_index"] += 1
            
            # Important: Don't set a dummy decision for execute_tool
            state["current_step_context"] = {}  # Clear the context entirely
        else:
            # For non-end decisions, update state as normal
            state["current_step_context"]["last_decision"] = decision.dict()

        # Add response to devops_agent_response
        state["devops_agent_response"].append(SystemMessage(content=response))
        
        return state

    except Exception as e:
        error_msg = f"Error in get_next_devops_action: {str(e)}"
        print(colored(error_msg, 'red'))
        if "devops_agent_response" not in state:
            state["devops_agent_response"] = []
        state["devops_agent_response"].append(SystemMessage(content=error_msg))
        return state
    
def _format_codebase_context(overview: str, file_tree: str, file_contents: Dict) -> str:
    """Format codebase context for LLM consumption."""
    return f"""Overview:
                {overview}

                File Structure:
                {file_tree}

                Relevant Files:
                {json.dumps(file_contents, indent=2) if file_contents else 'No file contents available'}
            """

def execute_tool(state: AgentGraphState) -> AgentGraphState:
    """
    Execute a tool based on the LLM's last decision.
    If decision is 'end', we do nothing here as that's handled in get_next_devops_action.
    """
    try:
        # Get decision from state
        if not state.get("current_step_context"):
            state["current_step_context"] = {}
            return state

        decision_data = state["current_step_context"].get("last_decision")
        if not decision_data:
            return state

        decision = LLMDecision(**decision_data)
                
        # Log start of tool execution with more visible formatting
        print(colored("\n" + "="*80, 'cyan'))
        print(colored("TOOL EXECUTION START", 'cyan'))
        print(colored(f"Tool Type: {decision.type}", 'cyan'))
        print(colored(f"Description: {decision.description}", 'cyan'))
        print(colored("="*80 + "\n", 'cyan'))
        
        log_interaction(state, "execute_tool_start", {
            "tool_type": decision.type,
            "description": decision.description,
            "content": decision.content,
            "reasoning": decision.reasoning
        })
        
        # Initialize tools
        tools = _initialize_tools(state)
        
        # Map decision types to tool functions
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
            "validate_command_output": "validate_command_output",
            "rollback_commits": "rollback_commits",
            "retrieve_integration_info": "integration_info",
            "end": "end_step"
        }
        
        # Verify tool type exists
        tool_func_name = tool_map.get(decision.type)
        if not tool_func_name:
            error_msg = f"Unknown tool type: {decision.type}"
            print(colored("\nERROR: " + error_msg, 'red'))
            raise ValueError(error_msg)
            
        # Verify tool function exists
        tool_func = getattr(tools, tool_func_name, None)
        if not tool_func:
            error_msg = f"Tool function not found: {tool_func_name}"
            print(colored("\nERROR: " + error_msg, 'red'))
            raise ValueError(error_msg)
        
        # Build tool inputs with better error handling
        try:
            inputs = {}
            if decision.type == "modify_code":
                print(colored("\nPreparing code modification...", 'yellow'))
                inputs["code"] = decision.content
                inputs["instructions"] = decision.description
            elif decision.type == "execute_command":
                print(colored("\nPreparing command execution...", 'yellow'))
                if not hasattr(decision, 'command') or not decision.command:
                    inputs["command"] = decision.content
                else:
                    inputs["command"] = decision.command
            elif decision.type == "retrieve_documentation":
                print(colored("\nPreparing documentation retrieval...", 'yellow'))
                inputs = {"query": decision.content} 
            elif decision.type == "ask_human_for_information":
                print(colored("\nPreparing human information request...", 'yellow'))
                inputs["question"] = decision.content
            elif decision.type == "ask_human_for_intervention":
                print(colored("\nPreparing human intervention request...", 'yellow'))
                inputs["explanation"] = decision.content
            elif decision.type == "run_file":
                print(colored("\nPreparing file execution...", 'yellow'))
                inputs["file_path"] = decision.content
            elif decision.type == "validate_output":
                print(colored("\nPreparing output validation...", 'yellow'))
                inputs["output"] = decision.content
                inputs["expected_behavior"] = decision.description
                inputs["validation_criteria"] = []
            elif decision.type == "validate_code_changes":
                # Find the last modify_code result in knowledge_sequence
                last_code_change = None
                for entry in reversed(state["knowledge_sequence"]):
                    if entry["action_type"] == "modify_code" and entry["result"]["status"] == "success":
                        last_code_change = entry["result"]["output"]
                        break
                
                inputs = {
                    "code": last_code_change if last_code_change else decision.content,
                    "instructions": decision.description,
                    "expected_changes": decision.content or ""
                }
            elif decision.type == "validate_file_output":
                print(colored("\nPreparing file output validation...", 'yellow'))
                inputs["file_content"] = decision.content
                inputs["expected_content"] = decision.description
            elif decision.type == "validate_command_output":
                print(colored("\nPreparing command output validation...", 'yellow'))
                inputs["command_output"] = decision.content
                inputs["expected_behavior"] = decision.description
            elif decision.type == "delete_file":
                print(colored("\nPreparing file deletion...", 'yellow'))
                inputs["file_path"] = decision.content
            elif decision.type == "create_file":
                if not decision.file_path:
                    # If file_path wasn't specified, we have an error
                    result = ToolResult(
                        status="error",
                        error="No file path specified for create_file operation"
                    )
                else:
                    inputs = {
                        "file_path": decision.file_path,
                        "content": decision.content or ""
                    }
            elif decision.type == "copy_template":
                print(colored("\nPreparing template copy...", 'yellow'))
                inputs["template_path"] = decision.content
            elif decision.type == "rollback_commits":
                print(colored("\nPreparing commit rollback...", 'yellow'))
                inputs["num_commits"] = int(decision.content) if decision.content else 1
            elif decision.type == "retrieve_integration_info":
                print(colored("\nPreparing integration information retrieval...", 'yellow'))
                inputs["query"] = decision.content
                inputs["integration_name"] = getattr(decision, "integration_name", decision.description)
                        
            # Execute tool with more detailed error handling
            print(colored("\nExecuting tool...", 'yellow'))
            result = tool_func(**inputs)
            
            # Display tool execution results
            print(colored("\nTOOL EXECUTION RESULT:", 'green'))
            print(colored(f"Status: {result.status}", 'green' if result.status == "success" else 'red'))
            if result.output:
                print(colored("Output:", 'green'))
                print(result.output)
            if result.error:
                print(colored("Error:", 'red'))
                print(result.error)
            
            # Create and log knowledge entry
            knowledge_update = {
                "timestamp": datetime.now().isoformat(),
                "action_type": tool_func_name,
                "action": str(inputs),
                "result": result.dict() if hasattr(result, 'dict') else {
                    "status": result.status,
                    "output": getattr(result, 'output', None),
                    "error": getattr(result, 'error', None)
                },
                "context": {
                    "step_number": state["current_step_index"] + 1,
                    "step_description": state["plan_steps"][state["current_step_index"]].description,
                    "attempt_number": state["current_step_attempts"] + 1,
                    "reasoning": decision.reasoning
                }
            }
            
            # Update state
            state["knowledge_sequence"].append(knowledge_update)
            state["current_step_attempts"] += 1
            
            # Log the execution result
            log_interaction(state, "execute_tool_result", {
                "tool_result": result.dict() if hasattr(result, 'dict') else {
                    "status": result.status,
                    "output": getattr(result, 'output', None),
                    "error": getattr(result, 'error', None)
                },
                "knowledge_update": knowledge_update
            })
            
            print(colored("\n" + "="*80, 'cyan'))
            print(colored("TOOL EXECUTION COMPLETE", 'cyan'))
            print(colored("="*80 + "\n", 'cyan'))

            return state

        except Exception as ex:
            error_msg = f"Error during tool execution:\nType: {type(ex).__name__}\nDetails: {str(ex)}"
            print(colored("\nTOOL EXECUTION ERROR:", 'red'))
            print(colored(error_msg, 'red'))
            print(colored("\nFull error context:", 'red'))
            print(colored(f"Tool type: {decision.type}", 'yellow'))
            print(colored(f"Description: {decision.description}", 'yellow'))
            print(colored("Input content:", 'yellow'))
            print(decision.content)
            
            log_interaction(state, "execute_tool_error", {
                "error": str(ex),
                "error_type": type(ex).__name__,
                "type": decision.type,
                "description": decision.description,
                "content": decision.content
            })
            
            state["current_step_attempts"] += 1
            if "devops_agent_response" not in state:
                state["devops_agent_response"] = []
            state["devops_agent_response"].append(SystemMessage(content=error_msg))
            
            return state

    except Exception as e:
        error_msg = f"Critical error in execute_tool:\nType: {type(e).__name__}\nDetails: {str(e)}"
        print(colored("\nCRITICAL ERROR:", 'red', attrs=['bold']))
        print(colored(error_msg, 'red'))
        
        if "devops_agent_response" not in state:
            state["devops_agent_response"] = []
        state["devops_agent_response"].append(SystemMessage(content=error_msg))
        return state

def _initialize_tools(state: AgentGraphState) -> DevOpsTools:
    """Initialize DevOpsTools if not present."""
    if not state.get("tools"):
        tools = DevOpsTools(
            working_directory=state["current_directory"],
            subprocess_handler=state["subprocess_handler"],
            project_id=state["project_id"]
        )
        tools.set_forge(state["forge"])
        state["tools"] = tools
        
        print(colored("DevOps Agent 🤖: Initialized tools", 'green'))
        
    return state["tools"]
