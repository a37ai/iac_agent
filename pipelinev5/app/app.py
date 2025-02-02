from pathlib import Path
import os
import git
import shutil
import sys
import json
import logging
from termcolor import colored
from dotenv import load_dotenv
from agent_tools.system_mapper_tools import SystemMapper
from utils.general_helper_functions import configure_logger
from forge.forge_wrapper import ForgeWrapper
from utils.subprocess_handler import SubprocessHandler
from agent_graph.graph import create_graph, compile_workflow, initialize_state

# Initialize logging
logger = configure_logger(__name__)

# Server and model config
server = 'openai'
model = 'gpt-4o'
deepseek_model = 'deepseek-chat'
model_endpoint = None
iterations = 200


class Pipeline:
    def __init__(self, repo_path: str):
        load_dotenv()
        self.base_dir = Path(__file__).parent.parent.absolute()
        self.test_repos_path = self.base_dir / Path(os.getenv('LOCAL_CLONE_PATH'))
        self.system_maps_dir = self.base_dir / "system_maps"
        self.mapper = SystemMapper()
        self.system_map = None
        self.forge = None
        self.subprocess_handler = None

        # Create necessary directories
        self.system_maps_dir.mkdir(parents=True, exist_ok=True)
        self.test_repos_path.mkdir(parents=True, exist_ok=True)

    def initialize_subprocess_handler(self):
        """Initialize the subprocess handler."""
        if not self.subprocess_handler:
            self.subprocess_handler = SubprocessHandler(working_directory=self.test_repos_path)

    def initialize_forge(self):
        """Initialize Forge with Git repo setup."""
        if not self.forge:
            repo_path = self.test_repos_path
            git_dir = repo_path / ".git"
            
            if not git_dir.exists():
                print(colored("Initializing new git repository...", 'blue'))
                repo = git.Repo.init(repo_path)
                with repo.config_writer() as git_config:
                    git_config.set_value('user', 'name', 'forge-bot')
                    git_config.set_value('user', 'email', 'forge-bot@example.com')

                gitignore_path = repo_path / ".gitignore"
                if not gitignore_path.exists():
                    with open(gitignore_path, 'w') as f:
                        f.write("*.pyc\n__pycache__/\n.env\n.vscode/\n")
                    repo.index.add(['.gitignore'])
                    repo.index.commit("Initial commit")

            # Set up Forge history
            forge_history = repo_path / ".forge.input.history"
            if forge_history.is_dir():
                shutil.rmtree(forge_history)
            elif forge_history.exists():
                forge_history.unlink()
            forge_history.touch()

            self.forge = ForgeWrapper(
                auto_commit=True,
                git_root=str(repo_path)
            )

    def map_system(self) -> dict:
        """Generate and save system map."""
        print(colored("Mapping system...", 'blue'))
        self.system_map = self.mapper.generate_system_map()
        
        system_map_file = self.system_maps_dir / "system_map.json"
        with open(system_map_file, 'w') as f:
            json.dump(self.system_map, f, indent=2)
            
        return self.system_map

    def run_workflow(self, query: str) -> dict:
        """Run the complete workflow with the graph."""
        try:
            # Initialize components
            self.initialize_forge()
            self.initialize_subprocess_handler()

            # Create and compile workflow
            print(colored("Creating workflow graph...", 'blue'))
            graph = create_graph(
                server=server,
                model=model,
                deepseek_model=deepseek_model,
                model_endpoint=model_endpoint,
                query=query,
                repo_path=str(self.test_repos_path),
                os="Mac"
            )
            
            workflow = compile_workflow(graph)

            # Initialize state
            initial_state = initialize_state(
                query=query,
                repo_path=str(self.test_repos_path)
            )

            # Add forge and subprocess handler to state
            initial_state["forge"] = self.forge
            initial_state["subprocess_handler"] = self.subprocess_handler

            print(colored("\nStarting workflow execution...", 'green'))
            
            # Execute workflow
            limit = {"recursion_limit": iterations}
            for event in workflow.stream(initial_state, limit):
                if event.get("end_chain") == "end_chain":
                    print(colored("\nWorkflow completed successfully", 'green'))
                    break

            return {
                "final_state": event
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            raise

# def main():
#     # Load environment variables
#     load_dotenv()

#     # Get repo path from environment
#     repo_path = os.getenv('LOCAL_CLONE_PATH')
#     if not repo_path:
#         print(colored("Error: LOCAL_CLONE_PATH environment variable not set", 'red'))
#         sys.exit(1)

#     # Initialize pipeline
#     print(colored("\n=== Initializing Pipeline ===", 'blue'))
#     pipeline = Pipeline(repo_path)

#     while True:
#         try:
#             # Get user query
#             print(colored("\nEnter your infrastructure request (or 'exit' to quit):", 'cyan'))
#             query = input("> ").strip()

#             if query.lower() == 'exit':
#                 break
#             if not query:
#                 print(colored("Please provide a query", 'yellow'))
#                 continue

#             # Run workflow
#             result = pipeline.run_workflow(query)
            
#             # Display final status
#             if result.get("final_state", {}).get("completed_steps"):
#                 steps = len(result["final_state"]["completed_steps"])
#                 print(colored(f"\nCompleted {steps} steps successfully", 'green'))
            
#         except KeyboardInterrupt:
#             print(colored("\nOperation cancelled by user", 'yellow'))
#             break
#         except Exception as e:
#             print(colored(f"\nError: {str(e)}", 'red'))
#             logger.error(f"Error in main loop: {str(e)}")

def main():
    # Load environment variables
    load_dotenv()

    # Get repo path from environment
    repo_path = os.getenv('LOCAL_CLONE_PATH')
    if not repo_path:
        print(colored("Error: LOCAL_CLONE_PATH environment variable not set", 'red'))
        sys.exit(1)

    # Initialize pipeline
    print(colored("\n=== Initializing Pipeline ===", 'blue'))
    pipeline = Pipeline(repo_path)

    try:
        # Get a single user query (no while loop)
        print(colored("\nEnter your infrastructure request:", 'cyan'))
        query = input("> ").strip()

        if not query:
            print(colored("Please provide a query", 'yellow'))
            sys.exit(1)

        # Run workflow once
        result = pipeline.run_workflow(query)
            
        # Display final status
        if result.get("final_state", {}).get("completed_steps"):
            steps = len(result["final_state"]["completed_steps"])
            print(colored(f"\nCompleted {steps} steps successfully", 'green'))
            
    except KeyboardInterrupt:
        print(colored("\nOperation cancelled by user", 'yellow'))
    except Exception as e:
        print(colored(f"\nError: {str(e)}", 'red'))
        logger.error(f"Error in main loop: {str(e)}")

if __name__ == "__main__":
    main()