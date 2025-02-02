import json
from termcolor import colored
from datetime import datetime
from langchain_core.messages import SystemMessage
from states.state import AgentGraphState, Memory
from agent_tools.system_mapper_tools import SystemMapper
from agent_tools.memory_tools import MemoryTools
import os
import logging

logger = logging.getLogger(__name__)

def system_mapper_agent(state: AgentGraphState) -> AgentGraphState:
    """Agent responsible for system mapping and memory management."""
    try:
        print(colored("\nSystem Mapper Agent 🗺️: Starting system analysis", 'blue'))
        mapper = SystemMapper(memory_context=state.get("memory_context"))
        
        # Get repository URL
        repo_url = os.getenv('REPO_URLS', '').strip()
        if not repo_url:
            print(colored("No repository URL provided", 'yellow'))
            return state

        # Check memory context for existing analysis
        if (mapper.memory_context and 
            mapper.memory_context.past_repo_url == repo_url and
            mapper.memory_context.past_analyses):
            
            logger.info("Using cached analysis from Pinecone")
            state["codebase_overview"] = mapper.memory_context.past_overview
            state["file_tree"] = mapper.generate_file_tree()
            state["file_analyses"] = mapper.memory_context.past_analyses
            
            print(colored("\nMemory Query Results:", 'green'))
            print(colored(f"Last accessed: {mapper.memory_context.last_accessed}", 'cyan'))
            print(colored(f"Has analyses: {bool(mapper.memory_context.past_analyses)}", 'cyan'))
            print(colored(f"Has overview: {bool(mapper.memory_context.past_overview)}", 'cyan'))
            if mapper.memory_context.past_analyses:
                print(colored(f"Number of files analyzed: {len(mapper.memory_context.past_analyses)}", 'cyan'))
                print(colored("File paths:", 'cyan'))
                for path in mapper.memory_context.past_analyses.keys():
                    print(colored(f"  - {path}", 'cyan'))
            
            state["system_mapper_response"].append(
                SystemMessage(content="System mapping complete (using cached analysis)")
            )
            return state

        # Clone repositories if needed
        if not (mapper.memory_context and mapper.memory_context.past_repo_url == repo_url):
            mapper.clone_repositories()

        # Generate file tree
        file_tree = mapper.generate_file_tree()
        logger.info("Generated file tree")

        # Detect environments
        environments = mapper.detect_environments()

        # Collect and analyze files
        files_to_analyze = mapper.collect_files_to_analyze()
        file_analyses = {}
        errors = []

        for file_path in files_to_analyze:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                analysis = mapper.analyze_file(file_path, content)
                file_analyses[file_path] = analysis.dict()
            except Exception as e:
                errors.append(f"Error analyzing {file_path}: {str(e)}")

        # Generate repository overview using the analyzed data
        repo_overview = mapper._generate_overview(file_tree, file_analyses)

        # Update state with results
        state["codebase_overview"] = repo_overview
        state["file_tree"] = file_tree
        state["file_analyses"] = file_analyses

        # Store new memories in Pinecone
        memory_tools = MemoryTools()
        memories = []
        curr_time = datetime.now().isoformat()

        # Store file analyses as memories
        for file_path, analysis in file_analyses.items():
            memories.append(Memory(
                type="file_analysis",
                content=json.dumps(analysis),
                timestamp=curr_time,
                repo_path=repo_url,
                repo_type=state.get("repo_type", "mono"),
                file_path=str(file_path)
            ))

        # Store overview as memory
        if repo_overview:
            memories.append(Memory(
                type="repo_overview",
                content=repo_overview,
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
            SystemMessage(content="System mapping and memory storage complete")
        )
        
        return state

    except Exception as e:
        error_msg = f"Error in system_mapper_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        state["system_mapper_response"].append(SystemMessage(content=error_msg))
        return state