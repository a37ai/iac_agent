import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Module-level global variables for log file paths
EXECUTION_LOG_FILE = None
STATUS_LOG_FILE = None

def initialize_logging(state: Dict[str, Any]) -> str:
    """Initialize logging for a new execution, creating both a full log and a separate status log."""
    global EXECUTION_LOG_FILE, STATUS_LOG_FILE
    
    # Get the directory where test_repos is located
    test_repos_parent = Path(state["current_directory"]).parent / "test_repos"
    if test_repos_parent.exists():
        log_dir = test_repos_parent.parent / "logs" / "devops_agent"
    else:
        # Fallback if test_repos not found
        log_dir = Path(state["current_directory"]).parent / "logs" / "devops_agent"
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a more descriptive timestamp that includes date and time
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Create more descriptive filenames
    EXECUTION_LOG_FILE = os.path.join(log_dir, f"devops_execution_{timestamp}_full.log")
    STATUS_LOG_FILE = os.path.join(log_dir, f"devops_status_{timestamp}.log")
    
    # Write initial execution header for the full log
    with open(EXECUTION_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== DevOps Agent Execution Log ===\n")
        f.write(f"Started at: {datetime.now().isoformat()}\n")
        f.write(f"Working Directory: {state['current_directory']}\n")
        f.write(f"Total Steps: {len(state['plan_steps'])}\n\n")
        
        # Log initial plan
        f.write("=== Execution Plan ===\n")
        for i, step in enumerate(state['plan_steps'], 1):
            f.write(f"\nStep {i}:\n")
            f.write(f"Description: {step.description}\n")
            f.write(f"Type: {step.step_type}\n")
            f.write(f"Files: {', '.join(step.files)}\n")
        f.write("\n" + "="*80 + "\n\n")

    # Write initial header for the status log
    with open(STATUS_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("=== DevOps Agent Status Log ===\n")
        f.write(f"Started at: {datetime.now().isoformat()}\n\n")
    
    return EXECUTION_LOG_FILE

def log_interaction(state: Dict[str, Any], node_name: str, details: Dict):
    """Write logs to the global EXECUTION_LOG_FILE with better formatting."""
    global EXECUTION_LOG_FILE
    
    # Initialize logging if not already done
    if EXECUTION_LOG_FILE is None:
        initialize_logging(state)
    
    with open(EXECUTION_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Node: {node_name}\n")
        f.write(f"Step: {state['current_step_index'] + 1}/{len(state['plan_steps'])}\n")
        f.write(f"Attempt: {state['current_step_attempts']}\n")
        f.write(f"Total Attempts: {state['total_attempts']}\n\n")
        
        # Log step details
        if state['current_step_index'] < len(state['plan_steps']):
            current_step = state['plan_steps'][state['current_step_index']]
            f.write("Current Step Details:\n")
            f.write(f"Description: {current_step.description}\n")
            f.write(f"Type: {current_step.step_type}\n")
            f.write(f"Files: {', '.join(current_step.files)}\n\n")
        
        f.write("Action Details:\n")
        for key, value in details.items():
            f.write(f"{key}:\n")
            if isinstance(value, dict):
                f.write(json.dumps(value, indent=2) + "\n")
            elif isinstance(value, list):
                for item in value:
                    f.write(f"- {item}\n")
            else:
                f.write(f"{str(value)}\n")
            f.write("\n")
        
        # If we have knowledge_sequence, log a summary
        if state.get('knowledge_sequence'):
            f.write("\nKnowledge Sequence Summary:\n")
            f.write(f"Total Actions: {len(state['knowledge_sequence'])}\n")
            if state['knowledge_sequence']:
                last_action = state['knowledge_sequence'][-1]
                f.write("Last Action:\n")
                f.write(f"Type: {last_action.get('action_type', 'unknown')}\n")
                f.write(f"Status: {last_action.get('result', {}).get('status', 'unknown')}\n")
                if last_action.get('result', {}).get('error'):
                    f.write(f"Error: {last_action['result']['error']}\n")
        
        f.write("\n")

def log_status_update(tagline: str, summary: str):
    """Log a short 'Tagline' and 'Summary' to STATUS_LOG_FILE for quick status tracking."""
    global STATUS_LOG_FILE
    if not STATUS_LOG_FILE:
        return
    
    with open(STATUS_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Tagline: {tagline}\n")
        f.write(f"Summary: {summary}\n\n")
