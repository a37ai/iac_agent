from typing import Dict, Optional, List, Any
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import logging
import argparse
import sys
import json

# Local imports
from system_mapper import SystemMapper
from planning_workflow import start_planning
from human_replanning import start_replanning
from devops_agent import start_devops_agent, create_devops_workflow
from tools import DevOpsTools
from forge.forge_wrapper import ForgeWrapper
from plan_manager import save_plan
from typing import Literal 

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class SubprocessHandler:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.current_env = os.environ.copy()
        
    def execute_command(self, command: str, timeout: int = 300) -> Dict[str, Any]:
        """Execute a command and return the result."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.repo_path.resolve()),
                env=self.current_env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                'stdout': result.stdout,
                'stderr': result.stderr,
                'status': 'success' if result.returncode == 0 else 'error',
                'return_code': result.returncode
            }
        except subprocess.TimeoutExpired as e:
            return {
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'status': 'timeout',
                'return_code': -1
            }
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'status': 'error',
                'return_code': -1
            }
            
    def update_environment(self, env_vars: Dict[str, str]):
        """Update subprocess environment variables."""
        self.current_env.update(env_vars)

class Pipeline:
    def __init__(self, repo_path: str):
        """Initialize the pipeline."""
        load_dotenv()
        self.test_repos_path = Path(os.getenv('LOCAL_CLONE_PATH'))
        self.base_dir = Path(__file__).parent.absolute()
        self.system_maps_dir = self.base_dir / "system_maps"
        self.system_map = None
        self.subprocess_handler = SubprocessHandler(self.test_repos_path)
        self.forge = None
        self.mapper = SystemMapper()
        
        # Ensure system maps directory exists
        self.system_maps_dir.mkdir(exist_ok=True)
        
    def initialize_forge(self):
        """Initialize the forge wrapper."""
        if not self.forge:
            self.forge = ForgeWrapper()
            
    def map_system(self) -> Dict:
        """Map the system using SystemMapper and save the result."""
        self.system_map = self.mapper.generate_system_map()
        
        # Save the system map
        system_map_file = self.system_maps_dir / "system_map.json"
        with open(system_map_file, 'w') as f:
            json.dump(self.system_map, f, indent=2)
            
        return self.system_map
        
    def run(self, query: str) -> Dict[str, Any]:
        """Run the complete pipeline."""
        try:
            # Initialize forge
            self.initialize_forge()
            
            # Use existing system map if available, otherwise generate it
            if not self.system_map:
                logger.info("Starting System Mapping...")
                system_info = self.map_system()
            else:
                logger.info("Using existing system map")
                system_info = self.system_map
            
            # Initial Planning Phase
            logger.info("Starting Initial Planning Phase...")
            planning_result = start_planning(
                query=query,
                repo_path=str(self.test_repos_path),
                codebase_overview=system_info["repository_overview"],
                file_tree=str(system_info["file_tree"]),
                file_analyses=system_info["file_analyses"]
            )
            
            # Human Replanning Phase
            logger.info("Starting Human Replanning Phase...")
            replanning_result = start_replanning(
                repo_path=str(self.test_repos_path),
                codebase_overview=system_info["repository_overview"],
                file_tree=str(system_info["file_tree"]),
                file_analyses=system_info["file_analyses"]
            )
            
            # Run DevOps agent
            agent_result = start_devops_agent(
                plan_steps=replanning_result["plan"],
                repo_path=str(self.test_repos_path),
                codebase_overview=system_info["repository_overview"],
                file_tree=str(system_info["file_tree"]),
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
    
    # Get repo path from environment
    repo_path = os.getenv('LOCAL_CLONE_PATH')
    if not repo_path:
        print("Error: LOCAL_CLONE_PATH environment variable not set")
        sys.exit(1)
    
    try:
        # Initialize pipeline and map system first
        print("\n=== Initializing Pipeline ===")
        pipeline = Pipeline(repo_path)
        
        query = args.query
        if not query:
            print("\nPlease specify your infrastructure request:")
            query = input("> ").strip()
            if not query:
                print("Error: No query provided")
                sys.exit(1)
        
        # Run the rest of the pipeline
        result = pipeline.run(query)
        
        print("\n=== Pipeline Execution Complete ===")
        print(f"Steps Completed: {len(result['agent_result']['completed_steps'])}")
        print(f"Total Attempts: {result['agent_result']['total_attempts']}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 