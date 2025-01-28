from typing import TypedDict, List, Dict, Optional, Any, Annotated, Literal, Set
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
# from langchain_core.messages import add_messages
from agent_tools.tools import DevOpsTools

class MemoryState(TypedDict):
    messages: Annotated[list, add_messages]
    repo_path: str
    file_analyses: Dict[str, Any]
    repo_overview: Optional[str]
    file_tree: Dict
    repo_type: str
    memories: List[Dict]
    current_context: Optional[str]

class PlanStep(BaseModel):
    description: str
    content: str
    step_type: Literal["code", "command"]
    files: List[str] = []

class LLMDecision(BaseModel):
    """Flattened LLM decision."""
    type: str
    description: str
    content: str
    reasoning: str

class DevOpsState(TypedDict):
    messages: Annotated[list, add_messages]
    plan_steps: List[PlanStep]
    current_step_index: int
    completed_steps: List[Dict[str, Any]]
    codebase_overview: str
    file_tree: str
    current_directory: str
    iam_permissions: Dict[str, Any]
    credentials: Dict[str, str]
    current_step_attempts: int
    current_step_context: Dict[str, Any]
    knowledge_sequence: List[Dict[str, Any]]
    total_attempts: int
    subprocess_handler: Any
    forge: Any
    tools: Optional[DevOpsTools]


class Plan(BaseModel):
    steps: List[PlanStep]
    iteration: int = 1
    issues: List[str] = []

class EditRequest(BaseModel):
    """Structure for edit requests from users"""
    request: str
    rationale: Optional[str] = None

class ReplanningState(TypedDict):
    messages: Annotated[list, add_messages]
    edit_request: EditRequest
    repo_path: str
    codebase_overview: str
    file_tree: str
    file_analyses: Dict[str, str]
    plan: List[PlanStep]
    iteration: int

class FileAnalysis(BaseModel):
    """Schema for file analysis output"""
    main_purpose: str = Field(description="The main purpose and functionality of the file")
    key_components: List[str] = Field(description="Key components, classes, or functions")
    patterns: List[str] = Field(description="Important patterns and architectural decisions")
    devops_relevance: Dict[str, str] = Field(
        description="DevOps-specific aspects of the file",
        default_factory=lambda: {
            "configuration": "None",
            "infrastructure": "None",
            "pipeline": "None",
            "security": "None",
            "monitoring": "None"
        }
    )
    dependencies: List[str] = Field(
        description="External dependencies and integrations",
        default_factory=list
    )

class AnalyzerState(TypedDict):
    messages: Annotated[list, add_messages]
    current_file: Optional[str]
    file_analyses: Dict[str, FileAnalysis]
    repo_overview: Optional[str]
    file_tree: Dict
    repo_type: str
    errors: List[str]

class PlanStep(BaseModel):
    description: str
    content: str
    step_type: Literal["code", "command"]
    files: List[str] = []

class Question(BaseModel):
    question: str
    context: str
    default_answer: Optional[str] = None

class Questions(BaseModel):
    questions: List[Question]

class ValidationResult(BaseModel):
    status: Literal["complete", "needs_info", "has_issues"]
    missing_info: Optional[List[Question]] = None
    issue_explanation: Optional[str] = None

class ValidationContext(BaseModel):
    """Track context through validation iterations."""
    answers_history: Dict[str, List[str]] = {}  # Track answer changes
    previous_issues: List[str] = []
    relevant_files: List[str] = []
    iteration_context: Dict[int, Dict] = {}

class PlanningState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    repo_path: str
    codebase_overview: str
    file_tree: str
    file_analyses: Dict[str, str]
    questions: List[Question]
    answers: Dict[str, str]
    answered_questions: Set[str]  # Track which questions have been answered
    plan: List[PlanStep]
    validation_result: Optional[ValidationResult]
    iteration: int
    validation_context: ValidationContext

class UnifiedState(TypedDict):
    """Combined state for the unified workflow."""
    # Base state
    messages: Annotated[list, add_messages]
    repo_path: str
    
    # Memory state
    memories: List[Dict]
    
    # Analyzer state
    current_file: Optional[str]
    file_analyses: Dict[str, Any]
    repo_overview: Optional[str]
    file_tree: Dict
    repo_type: str
    errors: List[str]
    
    # Planning state
    query: str
    questions: List[Any]
    answers: Dict[str, str]
    answered_questions: Set[str]
    plan: List[Any]
    validation_result: Optional[Any]
    iteration: int
    
    # Replanning state
    edit_request: Optional[Any]
    
    # DevOps state
    current_step_index: int
    completed_steps: List[Dict[str, Any]]
    current_directory: str
    iam_permissions: Dict[str, Any]
    credentials: Dict[str, str]
    current_step_attempts: int
    current_step_context: Dict[str, Any]
    knowledge_sequence: List[Dict[str, Any]]
    total_attempts: int
    subprocess_handler: Any
    forge: Any
    tools: Optional[DevOpsTools]