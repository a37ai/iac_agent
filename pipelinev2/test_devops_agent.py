"""Test script for the DevOps agent workflow."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from forge.forge_wrapper import ForgeWrapper
from devops_agent import start_devops_agent
from pipeline import SubprocessHandler
from plan_manager import load_plan

def test_devops_agent():
    """Test the DevOps agent with an existing plan and system maps."""
    # Load environment variables
    load_dotenv()
    
    # Get workspace root path
    workspace_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    repo_path = workspace_root / "pipelinev2" / "test_repos"
    
    # Load system maps from JSON using absolute path
    system_maps_path = workspace_root / "pipelinev2" / "system_maps" / "system_map.json"
    with open(system_maps_path, "r") as f:
        system_map = json.load(f)
        
    # Extract required information
    codebase_overview = system_map["repository_overview"]
    file_tree = json.dumps(system_map["file_tree"], indent=2)
    file_analyses = system_map["file_analyses"]
    
    # Initialize tools with absolute path
    subprocess_handler = SubprocessHandler(repo_path)
    
    forge = ForgeWrapper(
            auto_commit = True,
            git_root = str(repo_path)
    )
    
    # Load plan and ensure all paths are absolute
    plan_steps = load_plan(repo_path)
    
    # Determine the working directory from the first file in the plan
    working_dir = None
    for step in plan_steps:
        if step.files:
            # Get the directory of the first file
            first_file = Path(step.files[0])
            if first_file.is_absolute():
                working_dir = str(first_file.parent)
            else:
                working_dir = str((repo_path / first_file).parent)
            break
    
    # If we found a working directory, update the subprocess handler
    if working_dir:
        subprocess_handler = SubprocessHandler(working_dir)
    
    # Run DevOps agent
    try:
        print("\n=== Starting DevOps Agent Test ===")
        result = start_devops_agent(
            plan_steps=plan_steps,
            repo_path=str(repo_path),
            codebase_overview=codebase_overview,
            file_tree=file_tree,
            subprocess_handler=subprocess_handler,
            forge=forge
        )
        
        # Print results
        print("\n=== Execution Results ===")
        print(f"Completed Steps: {len(result['completed_steps'])}")
        print(f"Total Attempts: {result['total_attempts']}")
        print(f"Log File: {result['log_file']}")
        
        # Print step details
        print("\nStep Details:")
        for i, step in enumerate(result['completed_steps'], 1):
            print(f"\nStep {i}:")
            print(f"Description: {step['description']}")
            print(f"Status: {step['status']}")
            if 'summary' in step:
                print(f"Summary: {step['summary'].get('summary', 'No summary available')}")
            if step.get('error'):
                print(f"Error: {step['error']}")
        
        # Print log file contents if requested
        if os.environ.get('SHOW_LOGS', '').lower() == 'true':
            print("\n=== Log File Contents ===")
            with open(result['log_file'], 'r', encoding='utf-8') as f:
                print(f.read())
                
    except Exception as e:
        print(f"\nError during execution: {str(e)}")
        raise

if __name__ == "__main__":
    test_devops_agent() 