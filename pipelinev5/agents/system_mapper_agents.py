import json
import os
from typing import Dict
from termcolor import colored
from datetime import datetime
from langchain_core.messages import SystemMessage
from states.state import AgentGraphState, Memory
from agent_tools.system_mapper_tools import SystemMapper
from agent_tools.memory_tools import MemoryTools

def system_mapper_agent(state: AgentGraphState) -> AgentGraphState:
    try:
        print(colored("\nSystem Mapper Agent 🗺️: Starting system analysis", 'blue'))
        mapper = SystemMapper(memory_context=state.get("memory_context"))
        system_map = mapper.generate_system_map()
        
        state["codebase_overview"] = system_map.get("repository_overview", "")
        state["file_tree"] = system_map.get("file_tree", {})
        state["file_analyses"] = system_map.get("file_analyses", {})
        
        # Only store memories if no previous analysis exists
        if repo_url := os.getenv('REPO_URLS', '').strip():
            memory_context = state.get("memory_context")
            if not memory_context or not memory_context.past_analyses:
                memory_tools = MemoryTools()
                memories = []
                
                curr_time = datetime.now().isoformat()
                
                # Store file analyses
                for file_path, analysis in state["file_analyses"].items():
                    memories.append(Memory(
                        type="file_analysis",
                        content=json.dumps(analysis),
                        timestamp=curr_time,
                        repo_path=repo_url,
                        repo_type=state.get("repo_type", "mono"),
                        file_path=str(file_path)
                    ))
                
                # Store overview
                if state["codebase_overview"]:
                    memories.append(Memory(
                        type="repo_overview",
                        content=state["codebase_overview"],
                        timestamp=curr_time,
                        repo_path=repo_url,
                        repo_type=state.get("repo_type", "mono"),
                        file_path=""
                    ))
                    
                print(colored("\nStoring memories in Pinecone...", 'cyan'))
                memory_tools.store_memories(memories)
                state["memories"] = memories
                print(colored(f"Stored {len(memories)} memories", 'green'))
        
        state["system_mapper_response"].append(
            SystemMessage(content="System mapping complete")
        )
        
        return state

    except Exception as e:
        error_msg = f"Error in system_mapper_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        state["system_mapper_response"].append(SystemMessage(content=error_msg))
        return state