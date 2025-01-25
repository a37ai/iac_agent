import json
import datetime
import os
from states.state import Question

def log_interaction(repo_path: str, node_name: str, input_data: dict, output_data: dict):
    """Log workflow interactions to a file."""
    log_dir = os.path.join(repo_path, "planning", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "workflow_interactions.txt")
    
    with open(log_file, 'a') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
        f.write(f"Node: {node_name}\n")
        f.write("\nInput:\n")
        f.write(json.dumps(input_data, indent=2))
        f.write("\n\nOutput:\n")
        f.write(json.dumps(output_data, indent=2))
        f.write("\n")

##############################################################################
# HELPER
##############################################################################

def get_answer_from_cli(question: Question) -> str:
    """Prompt the user for an answer via CLI."""
    print(f"\nQuestion: {question.question}")
    print(f"Context: {question.context}")
    print(f"Default: {question.default_answer}")
    user_input = input("\nYour answer (press Enter to use default): ").strip()
    return user_input if user_input else question.default_answer
