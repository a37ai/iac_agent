from typing import TypedDict, List, Dict, Optional, Annotated, Literal, Set
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
from pydantic import BaseModel
import json
import os
import logging
import datetime

# If you store the prompt in a separate file like planning_prompt.py, import it:
from prompts import planning_prompt
# Otherwise, just define the string inline.

##############################################################################
# DATA MODELS
##############################################################################

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

class Plan(BaseModel):
    steps: List[PlanStep]
    iteration: int = 1
    issues: List[str] = []

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

##############################################################################
# LOGGING
##############################################################################

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

##############################################################################
# WORKFLOW NODES
##############################################################################

def generate_questions(state: PlanningState) -> PlanningState:
    """
    Generate clarifying questions from the LLM about the request/codebase,
    but instruct the LLM to only produce new questions if absolutely necessary
    and not re-ask anything that was already answered.
    """
    input_data = {
        "query": state["query"],
        "iteration": state["iteration"],
        "validation_result": (
            state["validation_result"].dict() if state["validation_result"] else None
        ),
        "existing_answers": state["answers"]
    }
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
    # Build a direct prompt telling the LLM what we already know
    # and to only ask for absolutely critical new details if missing
    question_prompt = PromptTemplate(
        input_variables=["query", "answers", "codebase_overview"],
        template="""
You are a DevOps expert. The user has asked:
{query}

So far, the user has provided the following clarifications:
{answers}

Codebase overview:
{codebase_overview}

If there is any absolutely critical missing information that you cannot infer 
from the code or from the user's existing answers, ask it now. 
If there is nothing critical missing, return an empty "questions" list.

Return your response in valid JSON with exactly this structure:
{{
  "questions": [
    {{
      "question": "...",
      "context": "Why we need it",
      "default_answer": "A recommended default"
    }}
  ]
}}

If no questions are needed, return:
{{
  "questions": []
}}
"""
    )
    
    # If we have an existing validation_result saying "has_issues" or "needs_info",
    # we incorporate that context. Otherwise we just go with the prompt above.
    if state["validation_result"] and state["validation_result"].status in ("needs_info", "has_issues"):
        # If there's already a list of missing info from validation, pass that to the LLM.
        # However, we instruct it not to re-ask what's answered.
        issues_context = ""
        if state["validation_result"].issue_explanation:
            issues_context = f"Issues: {state['validation_result'].issue_explanation}"

        # Merge it into the question prompt
        user_prompt = f"""
{question_prompt.template}

Additional context from validation:
{issues_context}

Missing info from validation (if any):
{json.dumps(state["validation_result"].missing_info or [], indent=2)}
"""
    else:
        user_prompt = question_prompt.template
    
    # Invoke the LLM
    response = llm.with_structured_output(Questions).invoke(
        user_prompt.format(
            query=state["query"],
            answers=json.dumps(state["answers"], indent=2),
            codebase_overview=state["codebase_overview"]
        )
    )
    
    # If the LLM yields no questions or only empty "questions": [], skip
    new_questions = response.questions if response.questions else []
    
    # For each new question, gather an answer from the user
    for q in new_questions:
        # Actually ask the user at the CLI
        user_answer = get_answer_from_cli(q)
        state["answers"][q.question] = user_answer
        state["answered_questions"].add(q.question)
    
    # We'll store all newly generated questions for logging
    state["questions"] = new_questions
    
    # Log the interaction
    output_data = {
        "questions": [q.dict() for q in new_questions],
        "answers_after_generation": state["answers"]
    }
    log_interaction(state["repo_path"], "generate_questions", input_data, output_data)
    
    return state

def create_plan(state: PlanningState) -> PlanningState:
    """
    Create an implementation plan based on the user query, codebase, 
    and the clarifications the user has provided so far. 
    We incorporate all user answers into the final plan prompt 
    so the LLM does not re-ask them.
    """
    input_data = {
        "query": state["query"],
        "answers": state["answers"],
        "iteration": state["iteration"],
        "validation_result": (
            state["validation_result"].dict() if state["validation_result"] else None
        )
    }
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
    # Build the final plan prompt, injecting the user answers at the end
    plan_text = planning_prompt.format(
        query=state["query"],
        codebase_overview=state["codebase_overview"],
        file_tree=state["file_tree"],
        file_analyses=json.dumps(state["file_analyses"], indent=2),
        answers=json.dumps(state["answers"], indent=2)
    )
    
    # Call the model to produce a plan
    response = llm.with_structured_output(Plan).invoke(plan_text)
    
    state["plan"] = response.steps
    state["iteration"] += 1
    
    # Persist the plan using your plan manager
    from plan_manager import save_plan
    save_plan(state["plan"], state["repo_path"])
    
    # Log the interaction
    log_interaction(
        state["repo_path"],
        "create_plan",
        input_data,
        {
            "plan": [step.dict() for step in state["plan"]],
            "iteration": state["iteration"]
        }
    )
    
    return state

def validate_plan(state: PlanningState) -> PlanningState:
    """
    Validate the current plan. If it's complete, mark "complete".
    If there's absolutely critical missing info, mark "needs_info".
    If there are major issues, mark "has_issues". 
    The LLM is again told that the user has already answered certain questions,
    so it should not re-ask them unless it's brand new info critical to success.
    """
    input_data = {
        "plan": [step.dict() for step in state["plan"]],
        "iteration": state["iteration"],
        "answers": state["answers"]
    }
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
    # Build a summary of user answers & the plan to date
    context = {
        "iteration": state["iteration"],
        "answers": state["answers"],
        "answered_questions": list(state["answered_questions"]),
        "validation_context": state["validation_context"].dict()
    }
    
    validation_prompt = PromptTemplate(
        input_variables=["query", "plan", "context"],
        template="""
Review this implementation plan and the user's clarifications. 
Decide if the plan is ready to be executed.

Original Request:
{query}

Current Plan:
{plan}

User's Existing Answers & Context:
{context}

Return one of three statuses in valid JSON:
{{
  "status": "complete" | "needs_info" | "has_issues",
  "missing_info": [
     {{"question": "...", "context": "...", "default_answer": "..."}}
  ] or null,
  "issue_explanation": "Explanation of issues if has_issues"
}}

Rules:
1. If the plan is fully ready, set "status"="complete".
2. If critical info is missing, set "status"="needs_info" and specify what you absolutely must know.
   Do not re-ask questions if the user has already answered them.
3. If there's a major problem in the plan, set "status"="has_issues" and explain them in "issue_explanation".

Always aim to mark complete unless there's a real blocker.
No repeating or re-asking answered questions. 
"""
    )

    validation_response = llm.with_structured_output(ValidationResult).invoke(
        validation_prompt.format(
            query=state["query"],
            plan=json.dumps(input_data["plan"], indent=2),
            context=json.dumps(context, indent=2)
        )
    )
    
    state["validation_result"] = validation_response
    
    # Provide CLI feedback
    if validation_response.status == "complete":
        state["messages"].append(
            HumanMessage(content="\n=== Plan Validation Complete ===\nPlan is ready for execution.\n---")
        )
    elif validation_response.status == "needs_info":
        state["messages"].append(
            HumanMessage(content="\n=== Additional Critical Information Needed ===")
        )
        if validation_response.missing_info:
            for q in validation_response.missing_info:
                # Show the question to the user
                cli_msg = f"\nQuestion: {q.question}\nContext: {q.context}\nDefault: {q.default_answer}"
                state["messages"].append(HumanMessage(content=cli_msg))
    else:
        # has_issues
        msg = f"\n=== Plan Issues Found ===\n{validation_response.issue_explanation}\n---"
        state["messages"].append(HumanMessage(content=msg))
    
    # Log results
    output_data = {
        "validation_result": state["validation_result"].dict(),
        "messages": [m.content for m in state["messages"][-1:]]
    }
    log_interaction(state["repo_path"], "validate_plan", input_data, output_data)
    
    return state

def determine_next(state: PlanningState) -> Literal["generate_questions", "create_plan", "end"]:
    """
    Decide next step after validation.
    - If "complete", we are done (end).
    - If "needs_info" or "has_issues", gather clarifications again (generate_questions).
    """
    val = state["validation_result"]
    if val and val.status == "complete":
        return "end"
    elif val and val.status in ("needs_info", "has_issues"):
        return "generate_questions"
    else:
        # If there's no validation result or something unexpected, create a new plan
        return "create_plan"

##############################################################################
# WORKFLOW
##############################################################################

def create_planning_workflow() -> StateGraph:
    """
    Compose the planning workflow with:
      1) generate_questions -> 2) create_plan -> 3) validate -> (loop or end)
    """
    workflow = StateGraph(PlanningState)
    
    workflow.add_node("generate_questions", generate_questions)
    workflow.add_node("create_plan", create_plan)
    workflow.add_node("validate", validate_plan)
    
    # Initial entry point: gather clarifications
    workflow.set_entry_point("generate_questions")
    
    # Simple flow
    workflow.add_edge("generate_questions", "create_plan")
    workflow.add_edge("create_plan", "validate")
    
    # Validation can route to generate_questions for clarifications, 
    # or create_plan again, or end if complete
    workflow.add_conditional_edges(
        "validate",
        determine_next,
        {
            "generate_questions": "generate_questions",
            "create_plan": "create_plan",
            "end": END
        }
    )
    
    return workflow.compile()

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
    final_state = workflow.invoke(initial_state, config={"recursion_limit": 25})
    return final_state
