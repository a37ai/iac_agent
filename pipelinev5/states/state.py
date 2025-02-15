from typing import TypedDict, Annotated, Optional, Set, Dict, List, Any
from langgraph.graph import add_messages
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime
from pathlib import Path
import subprocess
import json
import pinecone
from langchain_openai import OpenAIEmbeddings



# Base Models
class Memory(BaseModel):
    type: str
    content: str
    timestamp: str
    repo_path: str
    repo_type: str
    file_path: str = ""

class MemoryContext(BaseModel):
    past_repo_url: Optional[str] = None
    last_accessed: Optional[str] = None 
    past_analyses: Dict[str, Any] = {}
    past_overview: Optional[str] = None

class Question(BaseModel):
    question: str
    context: str
    default_answer: Optional[str] = None

class ValidationResult(BaseModel):
    status: str
    missing_info: Optional[List[Question]] = None
    issue_explanation: Optional[str] = None

class ValidationContext(BaseModel):
    answers_history: Dict[str, List[str]] = {}
    previous_issues: List[str] = []
    relevant_files: List[str] = []
    iteration_context: Dict[int, Dict] = {}

class LLMDecision(BaseModel):
    type: str
    description: str
    content: str
    reasoning: str

class PlanStep(BaseModel):
    description: str
    content: str 
    step_type: str
    files: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "content": self.content,
            "step_type": self.step_type,
            "files": self.files
        }
    
    def json(self) -> str:
        return json.dumps(self.to_dict())

class ToolResult(BaseModel):
    status: str
    output: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "error": self.error
        }

class EditRequest(BaseModel):
    """Structure for edit requests from users"""
    request: str
    rationale: Optional[str] = None
    
class AgentGraphState(TypedDict):
    # Only annotate actual message fields
    system_mapper_response: Annotated[list, add_messages]
    search_query_generator_response: Annotated[list, add_messages]
    validate_search_query_response: Annotated[list, add_messages]
    plan_validator_response: Annotated[list, add_messages]
    question_generator_response: Annotated[list, add_messages]
    plan_creator_response: Annotated[list, add_messages]
    replanning_response: Annotated[list, add_messages]
    devops_agent_response: Annotated[list, add_messages]


    memory_agent_response: Annotated[list, add_messages]
    memory_context: Optional[MemoryContext] = None
    memories: List[Memory] = []
    pinecone_index: Optional[Any] = None
    embeddings_model: Optional[OpenAIEmbeddings] = None

    # Regular fields without message annotation
    query: str
    repo_path: str
    codebase_overview: str
    file_tree: Dict[str, Any]
    file_analyses: Dict[str, Dict]
    questions: List[Question]
    answers: Dict[str, str]
    answered_questions: Set[str]
    plan: List[PlanStep]
    validation_result: Optional[ValidationResult]
    validation_context: ValidationContext
    plan_steps: List[PlanStep]
    current_step_index: int
    completed_steps: List[Dict[str, Any]]
    current_directory: str
    current_step_attempts: int
    current_step_context: Dict[str, Any]
    knowledge_sequence: List[Dict[str, Any]]
    total_attempts: int
    subprocess_handler: Any
    forge: Any
    tools: Any
    iteration: int
    credentials: Dict[str, str]

    github_info: Optional[str]
    github_owner: Optional[str]
    github_repo: Optional[str]
    needs_github: bool
    github_focus: List[str]

    compression_agent_response: Annotated[list, add_messages]
    compression_decision: Optional[Dict[str, Any]] = None
    file_analyses_compressed: Optional[Dict[str, Dict]] = None


def get_agent_graph_state(state: AgentGraphState, state_key: str):
    """Get specific state components based on key."""
    # Planning workflow getters
    if state_key == "question_generator_all":
        return state.get("question_generator_response", [])
    elif state_key == "question_generator_latest":
        responses = state.get("question_generator_response", [])
        return responses[-1] if responses else None
    elif state_key == "plan_creator_all":
        return state.get("plan_creator_response", [])
    elif state_key == "plan_creator_latest":
        responses = state.get("plan_creator_response", [])
        return responses[-1] if responses else None
    elif state_key == "plan_validator_all":
        return state.get("plan_validator_response", [])
    elif state_key == "plan_validator_latest":
        responses = state.get("plan_validator_response", [])
        return responses[-1] if responses else None
    
    return None

# Initialize state with empty lists for message fields
state = {
    "memory_agent_response": [],
    "memory_context": None,
    "memories": [],
    "pinecone_index": None,
    "embeddings_model": None,

    "messages": [],
    "question_generator_response": [],
    "plan_creator_response": [],
    "plan_validator_response": [],
    "replanning_response": [],
    "devops_agent_response": [],
    "repo_path": "",
    "codebase_overview": "",
    "file_tree": {},
    "file_analyses": {},
    "query": "",
    "questions": [],
    "answers": {},
    "answered_questions": set(),
    "plan": [],
    "validation_result": None,
    "validation_context": ValidationContext(),
    "plan_steps": [],
    "current_step_index": 0,
    "completed_steps": [],
    "current_directory": "",
    "current_step_attempts": 0,
    "current_step_context": {},
    "knowledge_sequence": [],
    "total_attempts": 0,
    "subprocess_handler": None,
    "forge": None,
    "tools": None,
    "iteration": 0,
    "credentials": {},

    "github_info": None,
    "github_owner": None,
    "github_repo": None,
    "needs_github": False,
    "github_focus": [],

    "compression_agent_response": [],
    "compression_decision": None,
    "file_analyses_compressed": None
    
}