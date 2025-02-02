import json
from typing import Dict
from termcolor import colored
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json
# from ai_models.deepseek_models import get_deepseek_ai_json
from states.state import AgentGraphState
from prompts.compression_prompts import COMPRESSION_AGENT_PROMPT

def compression_agent(state: AgentGraphState, model=None, deepseek_model=None, server=None) -> AgentGraphState:
    """
    Agent that analyzes and potentially compresses file analysis data based on relevance.
    """
    try:
        print(colored("\nCompression Agent 🗜️: Starting analysis...", 'cyan'))
        
        # Get available files from file_analyses
        available_files = list(state.get("file_analyses", {}).keys())
        if not available_files:
            print(colored("No files to analyze", 'yellow'))
            return state
            
        # Format files list for prompt
        files_str = "\n".join(available_files)
        
        # Get environment overview
        env_overview = state.get("codebase_overview", "No overview available")
        
        # Format the compression prompt
        prompt = COMPRESSION_AGENT_PROMPT.format(
            query=state["query"],
            available_files=files_str,
            env_overview=env_overview
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Analyze files and determine compression needs"}
        ]

        # # Get LLM decision based on number of files
        # if len(available_files) > 50:
        #     print(colored("Using DeepSeek model for large file set...", 'cyan'))
        #     llm = get_deepseel_ai_json(model=deepseek_model)
        # else:
        print(colored("Using OpenAI model for small file set...", 'cyan'))
        llm = get_open_ai_json(model=model)
        
        print(colored("Compression Agent 🗜️: Analyzing file relevance...", 'cyan'))
        ai_msg = llm.invoke(messages)
        
        try:
            decision = json.loads(ai_msg.content)
            
            # Validate required fields
            required_fields = ["compress", "selected_files", "rationale"]
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field: {field}")

            print(colored(f"Compression decision: {'Compress' if decision['compress'] else 'No compression needed'}", 'cyan'))
            print(colored(f"Rationale: {decision['rationale']}", 'cyan'))
            
            if decision["compress"]:
                # Create compressed version of file_analyses
                compressed_analyses = {
                    file_path: analysis 
                    for file_path, analysis in state["file_analyses"].items()
                    if file_path in decision["selected_files"]
                }
                
                # Store compressed analyses in state
                state["file_analyses_compressed"] = compressed_analyses
                print(colored(f"Compressed analysis from {len(state['file_analyses'])} to {len(compressed_analyses)} files", 'green'))
            else:
                print(colored("No compression needed, using full file analysis", 'green'))
                
            # Store the compression decision
            state["compression_decision"] = decision

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response from LLM: {str(e)}"
            print(colored(error_msg, 'red'))
            raise
            
        except ValueError as e:
            error_msg = f"Invalid response format: {str(e)}"
            print(colored(error_msg, 'red'))
            raise

        if "compression_agent_response" not in state:
            state["compression_agent_response"] = []
        state["compression_agent_response"].append(
            SystemMessage(content=ai_msg.content)
        )
        
        return state

    except Exception as e:
        error_msg = f"Error in compression_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        if "compression_agent_response" not in state:
            state["compression_agent_response"] = []
        state["compression_agent_response"].append(SystemMessage(content=error_msg))
        return state