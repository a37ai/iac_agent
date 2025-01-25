from typing import Dict
import os
from termcolor import colored
from langchain_core.messages import SystemMessage
from states.state import AgentGraphState, Memory
from agent_tools.memory_tools import MemoryTools
from datetime import datetime

def memory_agent(state: AgentGraphState) -> AgentGraphState:
    """Agent responsible for managing repository memory."""
    try:
        print(colored("\nMemory Agent 🧠: Initializing", 'blue'))
        tools = MemoryTools()

        # Get repo URL
        repo_url = os.getenv('REPO_URLS', '').strip()
        if not repo_url:
            print(colored("No repository URL provided", 'yellow'))
            return state

        print(colored(f"Querying memories for: {repo_url}", 'cyan'))
        memory_context = tools.query_memories(repo_url)

        # Only proceed if this is a new repository or the URLs match exactly
        if memory_context.past_repo_url and memory_context.past_repo_url != repo_url:
            print(colored(f"Found different repository in memory: {memory_context.past_repo_url}", 'yellow'))
            print(colored("Clearing existing memory context", 'yellow'))
            memory_context = None
            
        state["memory_context"] = memory_context

        # Print memory details
        if memory_context and memory_context.past_repo_url:
            print(colored("\nMemory Query Results:", 'green'))
            print(colored(f"Last accessed: {memory_context.last_accessed}", 'cyan'))
            print(colored(f"Has analyses: {bool(memory_context.past_analyses)}", 'cyan'))
            print(colored(f"Has overview: {bool(memory_context.past_overview)}", 'cyan'))
            if memory_context.past_analyses:
                print(colored(f"Number of files analyzed: {len(memory_context.past_analyses)}", 'cyan'))
                print(colored("File paths:", 'cyan'))
                for path in memory_context.past_analyses.keys():
                    print(colored(f"  - {path}", 'cyan'))
        else:
            print(colored("No previous analysis found for this repository", 'yellow'))

        state["memory_agent_response"].append(
            SystemMessage(content="Memory retrieval complete")
        )
        return state

    except Exception as e:
        error_msg = f"Error in memory_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        state["memory_agent_response"].append(SystemMessage(content=error_msg))
        return state