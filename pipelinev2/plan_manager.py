from typing import List, Dict, Any
from pydantic import BaseModel
import json
import os
from pathlib import Path
from typing import Literal

class PlanStep(BaseModel):
    description: str
    content: str
    step_type: Literal["code", "command"]
    files: List[str] = []

def save_plan(plan_steps: List[PlanStep], repo_path: str) -> None:
    """Save plan to a consistent location."""
    planning_dir = Path(repo_path) / "planning"
    planning_dir.mkdir(exist_ok=True)
    
    plan_file = planning_dir / "current_plan.json"
    plan_data = {"steps": [step.dict() for step in plan_steps]}
    
    with open(plan_file, 'w') as f:
        json.dump(plan_data, f, indent=2)

def load_plan(repo_path: str) -> List[PlanStep]:
    """Load plan from the consistent location."""
    plan_file = Path(repo_path) / "planning" / "current_plan.json"
    
    with open(plan_file, 'r') as f:
        plan_data = json.load(f)
        
    return [PlanStep(**step) for step in plan_data["steps"]] 