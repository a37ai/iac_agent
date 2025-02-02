import json
from typing import TypedDict, Annotated
from termcolor import colored
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json, get_open_ai_json_v2
from ai_models.cerebras_models import get_cerebras_json
from ai_models.deepseek_models import get_deepseek_groq_json
from states.state import AgentGraphState, Question, ValidationResult, PlanStep
from prompts.planning_prompts import (
    validation_prompt_template,
    validation_prompt_template_with_github,
    planning_prompt_template,
    planning_prompt_template_with_github,
    question_generator_prompt_template,
    question_generator_prompt_template_with_github,
    QUESTION_WITH_ADDITIONAL_CONTEXT_PROMPT_WITH_GITHUB,
    QUESTION_WITH_ADDITIONAL_CONTEXT_PROMPT
)

def question_generator_agent(state: AgentGraphState, prompt=None, model=None, server=None, feedback=None, os=None):
    """
    Generate clarifying questions from the LLM about the request/codebase.
    Only produces new questions if absolutely necessary and avoids re-asking answered questions.
    """
    try:
        # Select appropriate prompt based on GitHub info presence
        if state.get("github_info"):
            prompt = question_generator_prompt_template_with_github
        else:
            prompt = question_generator_prompt_template
            
        # Build context from state
        input_data = {
            "query": state["query"],
            "answers": state["answers"],
            "codebase_overview": state["codebase_overview"],
            "github_info": state.get("github_info", "No GitHub information available"),
            "os": os
        }

        # Handle validation context if present
        if (state["validation_result"] and 
            state["validation_result"].status in ("needs_info", "has_issues")):
            
            issues_context = ""
            if state["validation_result"].issue_explanation:
                issues_context = f"Issues: {state['validation_result'].issue_explanation}"

            # Handle missing_info if present
            missing_info = []
            if state["validation_result"].missing_info:
                if isinstance(state["validation_result"].missing_info[0], dict):
                    # If already dictionaries, use as is
                    missing_info = state["validation_result"].missing_info
                else:
                    # Convert Question objects to dictionaries
                    missing_info = [q.dict() for q in state["validation_result"].missing_info]

            if state.get("github_info"):
                user_prompt = QUESTION_WITH_ADDITIONAL_CONTEXT_PROMPT_WITH_GITHUB.format(
                    base_prompt=prompt,
                    issues_context=issues_context,
                    github_info=state["github_info"],
                    missing_info=json.dumps(missing_info, indent=2),
                    os=os
                )
            else:
                user_prompt = QUESTION_WITH_ADDITIONAL_CONTEXT_PROMPT.format(
                    base_prompt=prompt,
                    issues_context=issues_context,
                    missing_info=json.dumps(missing_info, indent=2),
                    os=os
                )
        else:
            user_prompt = prompt.format(**input_data)

        messages = [
            {"role": "system", "content": user_prompt},
            {"role": "user", "content": "Please generate any necessary questions"}
        ]

        if server == 'openai':
            # llm = get_open_ai_json(model=model, temperature=0.1)
            llm = get_open_ai_json(model=model)

        
        ai_msg = llm.invoke(messages)
        response = ai_msg.content
        
        # Parse response and get questions
        response_data = json.loads(response)
        
        # Convert dictionaries to Question objects
        new_questions = [Question(**q) for q in response_data.get("questions", [])]
        
        # Get answers from user for each question
        for q in new_questions:
            print(colored(f"\nQuestion: {q.question}", 'cyan'))
            print(colored(f"Context: {q.context}", 'blue'))
            if q.default_answer:
                print(colored(f"Default: {q.default_answer}", 'yellow'))
            
            user_answer = input(colored("Your answer: ", 'green')).strip()
            if not user_answer and q.default_answer:
                user_answer = q.default_answer
            
            state["answers"][q.question] = user_answer
            state["answered_questions"].add(q.question)
        
        # Store questions as dictionaries in state
        state["questions"] = [q.dict() for q in new_questions]
        state["question_generator_response"].append(SystemMessage(content=response))
        
        print(colored(f"Question Generator 🤔: Generated {len(new_questions)} questions", 'magenta'))
        
        return state

    except Exception as e:
        error_msg = f"Error in question_generator_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        if "question_generator_response" not in state:
            state["question_generator_response"] = []
        state["question_generator_response"].append(SystemMessage(content=error_msg))
        return state

def plan_creator_agent(state: AgentGraphState, prompt=None, model=None, server=None, feedback=None, os=None):
    """Create an implementation plan based on the user query and answers."""
    try:
        # Select appropriate prompt based on GitHub info presence
        if state.get("github_info"):
            prompt = planning_prompt_template_with_github if prompt is None else prompt
        else:
            prompt = planning_prompt_template if prompt is None else prompt

        # Prepare validation feedback
        validation_feedback = ""
        if state.get("validation_result") and state["validation_result"].status == "has_issues":
            validation_feedback = f"""
Previous plan had the following issues that need to be addressed:
{state['validation_result'].issue_explanation}

Please revise the plan to fix these issues.
"""
        else:
            validation_feedback = "No validation issues to address."
        
        # print("Compression decision:", state.get("compression_decision"))
        # print("File analyses:", state.get("file_analyses"))
        # print("Compressed analyses:", state.get("file_analyses_compressed"))

        file_analyses = state["file_analyses"]
        if state.get("compression_decision") and state["compression_decision"].get("compress"):
            file_analyses = state["file_analyses_compressed"]

        # Format context for LLM
        plan_context = {
            "query": state["query"],
            "codebase_overview": state.get("codebase_overview", ""),
            "file_tree": state.get("file_tree", ""),
            "file_analyses": file_analyses,  # Using potentially compressed analyses
            "answers": state.get("answers", {}),
            "github_info": state.get("github_info", ""),
            "validation_feedback": validation_feedback,
            "os": os
        }

        messages = [
            {"role": "system", "content": prompt.format(**plan_context)},
            {"role": "user", "content": json.dumps(plan_context)}
        ]

        if server == 'openai':
            # llm = get_deepseek_groq_json()
            # llm = get_open_ai_json_v2()
            llm = get_cerebras_json()

        
        # print("Messages being sent to Cerebras:")
        # print(json.dumps(messages, indent=2))
        ai_msg = llm.invoke(messages)
        response = ai_msg.content
        
        # Parse response and convert to PlanStep objects
        plan_data = json.loads(response)
        plan_steps = [PlanStep(**step) for step in plan_data.get("steps", [])]
        
        # Update state
        state["plan"] = plan_steps
        state["plan_steps"] = plan_steps
        
        # Don't reset validation_result here anymore since we need it for feedback
        state["iteration"] = state.get("iteration", 0) + 1
        state["plan_creator_response"].append(SystemMessage(content=response))
        
        print(colored(f"Plan Creator 📝: Generated plan with {len(plan_steps)} steps", 'magenta'))
        print(colored(f"Iteration: {state['iteration']}", 'blue'))
        
        return state

    except Exception as e:
        error_msg = f"Error in plan_creator_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        state["plan_creator_response"].append(SystemMessage(content=error_msg))
        return state

def plan_validator_agent(state: AgentGraphState, prompt=None, model=None, server=None, feedback=None, os=None):
    """Validate the implementation plan."""
    try:
        # Select appropriate prompt based on GitHub info presence
        if state.get("github_info"):
            prompt = validation_prompt_template_with_github if prompt is None else prompt
        else:
            prompt = validation_prompt_template if prompt is None else prompt

        # Convert PlanSteps to dictionaries for JSON serialization
        plan_steps = [step.to_dict() for step in state["plan"]]
        
        context = {
            "iteration": state["iteration"],
            "answers": state["answers"],
            "answered_questions": list(state["answered_questions"]),
            "validation_context": state["validation_context"].dict() if state["validation_context"] else {},
            "github_info": state.get("github_info", ""),
            "os": os
        }

        # Format validation input
        validation_input = {
            "query": state["query"],
            "plan": json.dumps(plan_steps, indent=2),
            "context": json.dumps(context, indent=2),
            "github_info": state.get("github_info", "No GitHub information available"),
            "os": os
        }

        messages = [
            {"role": "system", "content": prompt.format(**validation_input)},
            {"role": "user", "content": json.dumps(validation_input)}
        ]

        if server == 'openai':
            # llm = get_open_ai_json(model=model)
            llm = get_cerebras_json()

        
        ai_msg = llm.invoke(messages)
        response = ai_msg.content
        
        validation_data = json.loads(response)
        
        # If missing_info is present, convert the dictionaries to Question objects
        if validation_data.get("missing_info"):
            validation_data["missing_info"] = [
                Question(**q if isinstance(q, dict) else q.dict())
                for q in validation_data["missing_info"]
            ]
            
        validation_result = ValidationResult(**validation_data)
        
        # Print validation status
        print(colored(f"\nPlan Validator 🔍: Status - {validation_result.status}", 'cyan'))
        if validation_result.issue_explanation:
            print(colored(f"Issues: {validation_result.issue_explanation}", 'yellow'))

        # Convert the ValidationResult to dict before storing in state
        state["validation_result"] = validation_result
        state["plan_validator_response"].append(SystemMessage(content=response))
        
        # If validation_result status is "needs_info", prepare questions for the question generator
        if validation_result.status == "needs_info" and validation_result.missing_info:
            # Convert Question objects to dictionaries for JSON serialization
            state["validation_result"].missing_info = [
                question.dict() for question in validation_result.missing_info
            ]
        
        return state

    except Exception as e:
        error_msg = f"Error in plan_validator_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        state["plan_validator_response"].append(SystemMessage(content=error_msg))
        return state

def determine_next_planning_step(state: AgentGraphState) -> str:
    """Route to the next step in the planning workflow."""
    val = state["validation_result"]
    if val and val.status == "complete":
        return "end"
    elif val and val.status in ("needs_info", "has_issues"):
        return "question_generator"
    else:
        return "plan_creator"
    
def end_node(state: AgentGraphState):
    """Clean up state before ending."""
    # Create a clean copy without message fields
    clean_state = {k: v for k, v in state.items() 
                  if not isinstance(v, list) or k not in [
                      'search_query_generator_response',
                      'validate_search_query_response', 
                      'plan_validator_response',
                      'question_generator_response',
                      'plan_creator_response',
                      'replanning_response',
                      'devops_agent_response',
                      'router_agent_response',  # Add new message fields to exclusion
                      'github_agent_response'
                  ]}
    clean_state["end_chain"] = "end_chain"
    return clean_state