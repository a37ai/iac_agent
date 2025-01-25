##############################################################################
# Existing `app.py` Code
##############################################################################
import os
import sys
import json
import logging
import argparse
from typing import TypedDict, List, Dict, Optional, Any
import subprocess

from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime

# Local imports from pipelinev4 (adjust as needed)
from agent_graph.graph import create_memory_graph, create_analyzer_workflow, create_planning_workflow
from states.state import MemoryState, AnalyzerState, PlanningState, ValidationContext, DevOpsState, PlanStep
from agent_tools.system_mapper import SystemMapper
from agent_graph.graph import create_devops_workflow, start_replanning 
from agent_tools.tools import DevOpsTools
from utils.plan_manager import save_plan  
from utils.general_helper_functions import configure_logger
from utils.logging_helper_functions import initialize_logging, log_interaction, log_status_update
from forge.forge_wrapper import ForgeWrapper

logger = configure_logger(__name__)

EXECUTION_LOG_FILE = None
STATUS_LOG_FILE = None

# Keep your existing code
def process_system_map(
    repo_path: str,
    file_analyses: Dict[str, Any],
    repo_overview: str,
    file_tree: Dict,
    repo_type: str = "mono"
) -> Dict:
    """Process and store system map information in memory."""
    workflow = create_memory_graph()
    
    # Initialize state
    initial_state = MemoryState({
        "messages": [],
        "repo_path": repo_path,
        "file_analyses": file_analyses,
        "repo_overview": repo_overview,
        "file_tree": file_tree,
        "repo_type": repo_type,
        "memories": [],
        "current_context": None
    })
    
    # Run workflow
    final_state = workflow.invoke(initial_state)
    
    return {
        "memories_stored": len(final_state["memories"]),
        "repo_path": repo_path,
        "repo_type": repo_type
    } 

def analyze_codebase(
    files: List[str],
    file_tree: Dict,
    repo_type: str = "mono"
) -> Dict:
    """Start the codebase analysis process"""
    workflow = create_analyzer_workflow()
    
    # Initialize state
    initial_state = AnalyzerState({
        "messages": [],
        "current_file": None,
        "file_analyses": {},
        "repo_overview": None,
        "file_tree": file_tree,
        "repo_type": repo_type,
        "errors": []
    })
    
    # Process each file
    final_state = initial_state
    for file in files:
        final_state["current_file"] = file
        final_state = workflow.invoke(final_state)
    
    return {
        "file_analyses": {k: v.dict() for k, v in final_state["file_analyses"].items()},
        "repo_overview": final_state["repo_overview"],
        "errors": final_state["errors"]
    }

def start_planning(
    query: str,
    repo_path: str,
    codebase_overview: str,
    file_tree: str,
    file_analyses: Dict[str, str],
    answers: Optional[Dict[str, str]] = None
) -> Dict:
    """
    Public entry point to run the planning workflow from your pipeline.
    """
    log_dir = os.path.join(repo_path, "planning", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    workflow = create_planning_workflow()
    
    # Initialize the planning state
    initial_state = PlanningState(
        messages=[],
        query=query,
        repo_path=repo_path,
        codebase_overview=codebase_overview,
        file_tree=file_tree,
        file_analyses=file_analyses,
        questions=[],
        answers=answers or {},
        answered_questions=set(),
        plan=[],
        validation_result=None,
        iteration=1,
        validation_context=ValidationContext()
    )
    
    # Invoke workflow
    final_state = workflow.invoke(initial_state, config={"recursion_limit": 50})
    return final_state


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
    
    # Convert plan steps to PlanStep objects if they're dictionaries
    normalized_steps = []
    for step in plan_steps:
        if isinstance(step, dict):
            normalized_steps.append(PlanStep(**step))
        else:
            normalized_steps.append(step)
    
    initial_state = DevOpsState(
        messages=[],
        plan_steps=normalized_steps,  # Use normalized steps
        current_step_index=0,
        completed_steps=[],
        codebase_overview=codebase_overview,
        file_tree=file_tree,
        current_directory=str(Path(repo_path).resolve()),
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
        
        try:
            # Add recursion_limit configuration here
            final_state = workflow.invoke(initial_state, config={"recursion_limit": 100})
        except Exception as workflow_error:
            # If workflow fails, we still want to write the summary
            final_state = initial_state  # Use initial state for summary if workflow fails
            logger.error(f"Workflow error: {workflow_error}")
            raise
        finally:
            # Always write summary, regardless of success or failure
            if EXECUTION_LOG_FILE and os.path.exists(os.path.dirname(EXECUTION_LOG_FILE)):
                with open(EXECUTION_LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write("\n=== Execution Summary ===\n")
                    f.write(f"Completed at: {datetime.now().isoformat()}\n")
                    f.write(f"Total Steps Completed: {len(final_state['completed_steps'])}/{len(normalized_steps)}\n")
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
        if EXECUTION_LOG_FILE and os.path.exists(os.path.dirname(EXECUTION_LOG_FILE)):
            with open(EXECUTION_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write("\n=== Execution Error ===\n")
                f.write(f"Error: {str(ex)}\n")
                f.write("=== End of Execution Log ===\n")
        raise


##############################################################################
# New Code from original pipeline.py integrated below
##############################################################################

class SubprocessHandler:
    """Handle subprocess execution with proper error handling and logging."""
    
    def __init__(self, working_directory: str):
        """Initialize with working directory."""
        self.working_directory = Path(working_directory).resolve()
    
    def execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, str]:
        """Execute a shell command and return the result."""
        try:
            # Ensure working directory exists
            if not self.working_directory.exists():
                return {
                    'status': 'error',
                    'stderr': f'Working directory does not exist: {self.working_directory}'
                }
            
            # Execute command in working directory
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.working_directory),
                capture_output=True,
                text=True,
                timeout=timeout if timeout else 300
            )
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'stdout': result.stdout
                }
            else:
                return {
                    'status': 'error',
                    'stderr': result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'stderr': f'Command timed out after {timeout} seconds'
            }
        except Exception as e:
            return {
                'status': 'error',
                'stderr': str(e)
            }

class Pipeline:
    def __init__(self, repo_path: str):
        """Initialize the pipeline."""
        load_dotenv()
        self.base_dir = Path(__file__).parent.parent.absolute()
        self.test_repos_path = self.base_dir / Path(os.getenv('LOCAL_CLONE_PATH'))
        
        # Setup some base directories
        self.system_maps_dir = self.base_dir / "system_maps"
        self.system_map = None
        
        # Subprocess handler for command execution
        self.subprocess_handler = SubprocessHandler(self.test_repos_path)
        
        # We'll store a Forge instance if needed
        self.forge = None
        
        # Create a SystemMapper to handle codebase mapping
        self.mapper = SystemMapper()

        # Ensure system maps directory exists
        self.system_maps_dir.mkdir(exist_ok=True)
            
    def initialize_forge(self):
        """Initialize the forge wrapper so that test_repos is its own .git repo."""
        import git
        import shutil

        if not self.forge:
            repo_path = self.test_repos_path  # e.g. pipelinev4/test_repos
            repo_path.mkdir(parents=True, exist_ok=True)

            # Make test_repos have its own .git if not present
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                repo = git.Repo.init(repo_path)
                with repo.config_writer() as git_config:
                    git_config.set_value('user', 'name', 'forge-bot')
                    git_config.set_value('user', 'email', 'forge-bot@example.com')

                # Create .gitignore so we have something to commit
                gitignore_path = repo_path / ".gitignore"
                if not gitignore_path.exists():
                    with open(gitignore_path, 'w') as f:
                        f.write("*.pyc\n__pycache__/\n.env\n.vscode/\n")

                repo.index.add(['.gitignore'])
                repo.index.commit("Initial commit with .gitignore")

            # Clean up or create the .forge.input.history
            forge_history = repo_path / ".forge.input.history"
            if forge_history.is_dir():
                shutil.rmtree(forge_history)
            elif forge_history.exists():
                forge_history.unlink()
            forge_history.touch()

            # Finally create the Forge wrapper using test_repos as the git_root
            self.forge = ForgeWrapper(
                auto_commit=True,
                git_root=str(repo_path),  # CRITICAL: force the sub-repo as the Git root
                # you can add other args (model, etc.)
            )

            
    def map_system(self) -> Dict[str, Any]:
        """Map the system using SystemMapper and save the result."""
        self.system_map = self.mapper.generate_system_map()
        
        # Save the system map
        system_map_file = self.system_maps_dir / "system_map.json"
        with open(system_map_file, 'w') as f:
            json.dump(self.system_map, f, indent=2)
            
        return self.system_map

    def run(self, query: str) -> Dict[str, Any]:
        """Run the complete pipeline flow: mapping, planning, replanning, devops agent."""
        try:
            # Initialize forge (if relevant)
            self.initialize_forge()
            
            # Use existing system map if available, otherwise generate it
            if not self.system_map:
                logger.info("Starting System Mapping...")
                system_info = self.map_system()
            else:
                logger.info("Using existing system map")
                system_info = self.system_map

            # 1) Start planning
            logger.info("Starting Initial Planning Phase...")
            planning_result = start_planning(
                query=query,
                repo_path=str(self.test_repos_path),
                codebase_overview=system_info["repository_overview"],
                file_tree=json.dumps(system_info["file_tree"]),
                file_analyses=system_info["file_analyses"]
            )
            
            # 2) Human Replanning
            logger.info("Starting Human Replanning Phase...")
            replanning_result = start_replanning(
                repo_path=str(self.test_repos_path),
                codebase_overview=system_info["repository_overview"],
                file_tree=json.dumps(system_info["file_tree"]),
                file_analyses=system_info["file_analyses"]
            )
            
            # 3) Run DevOps agent
            logger.info("Starting DevOps Agent execution...")
            
            # final_plan_steps = [PlanStep(**s) for s in replanning_result["plan"]]

            agent_result = start_devops_agent(
                plan_steps=replanning_result["plan"],
                repo_path=str(self.test_repos_path),
                codebase_overview=system_info["repository_overview"],
                file_tree=json.dumps(system_info["file_tree"]),
                subprocess_handler=self.subprocess_handler,
                forge=self.forge
            )

            return {
                "system_info": system_info,
                "planning_result": planning_result,
                "replanning_result": replanning_result,
                "agent_result": agent_result
            }
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Run the infrastructure planning pipeline')
    parser.add_argument('query', nargs='?', help='The infrastructure request/query')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()

    # Confirm local clone path
    repo_path = os.getenv('LOCAL_CLONE_PATH')
    if not repo_path:
        print("Error: LOCAL_CLONE_PATH environment variable not set")
        sys.exit(1)
    
    # Initialize pipeline
    print("\n=== Initializing Pipeline ===")
    pipeline = Pipeline(repo_path)

    # Prompt user for query if not provided
    query = args.query
    if not query:
        print("\nPlease specify your infrastructure request:")
        query = input("> ").strip()
        if not query:
            print("Error: No query provided")
            sys.exit(1)
    
    # Run the entire pipeline
    result = pipeline.run(query)
    
    print("\n=== Pipeline Execution Complete ===")
    print(f"Steps Completed: {len(result['agent_result']['completed_steps'])}")
    print(f"Total Attempts: {result['agent_result']['total_attempts']}")

# If you want your app to be runnable directly:
if __name__ == "__main__":
    main()
