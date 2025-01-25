import pytest
import json
import os
from pathlib import Path
from langchain_core.messages import SystemMessage
from agents.github_agents import github_agent
from prompts.github_agent_prompts import github_agent_prompt

@pytest.fixture
def base_state():
    """Create a complete base state fixture."""
    return {
        "query": "",  # Will be set in individual tests
        "repo_path": str(Path.cwd() / "test_repos"),
        "codebase_overview": "Sample test repository with basic infrastructure",
        "file_tree": {
            "app": {"main.py": "file", "config.yaml": "file"},
            "tests": {"test_main.py": "file"},
            ".github": {
                "workflows": {"ci.yml": "file"}
            }
        },
        "file_analyses": {
            "app/main.py": {
                "purpose": "Main application entry point",
                "dependencies": ["yaml", "os"]
            }
        },
        "questions": [],
        "answers": {},
        "answered_questions": set(),
        "plan": [],
        "validation_result": None,
        "validation_context": None,
        "plan_steps": [],
        "current_step_index": 0,
        "completed_steps": [],
        "current_directory": str(Path.cwd() / "test_repos"),
        "current_step_attempts": 0,
        "current_step_context": {},
        "knowledge_sequence": [],
        "total_attempts": 0,
        "subprocess_handler": None,
        "forge": None,
        "tools": None,
        "iteration": 0,
        "credentials": {
            "github_token": os.getenv("GITHUB_TOKEN", "dummy-token")
        },
        "github_owner": "test-owner",
        "github_repo": "test-repo",
        "needs_github": True,
        "github_focus": ["pull_requests", "issues"],
        "github_info": None,
        "github_agent_response": [],
        "system_mapper_response": [],
        "question_generator_response": [],
        "plan_creator_response": [],
        "plan_validator_response": [],
        "replanning_response": [],
        "devops_agent_response": []
    }

def test_github_agent_basic_functionality(base_state):
    """Test basic functionality of GitHub agent with standard inputs"""
    test_state = base_state.copy()
    test_state["query"] = "Check the open pull requests"
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert "github_info" in result_state
    assert isinstance(result_state["github_info"], str)
    assert len(result_state["github_agent_response"]) > 0
    assert isinstance(result_state["github_agent_response"][0], SystemMessage)

def test_github_agent_handles_missing_credentials(base_state):
    """Test GitHub agent's handling of missing credentials"""
    test_state = base_state.copy()
    test_state["credentials"] = {}
    test_state["query"] = "List all pull requests"
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert "github_info" in result_state
    assert "error" in str(result_state["github_info"]).lower()

def test_github_agent_handles_invalid_repo(base_state):
    """Test GitHub agent's handling of invalid repository information"""
    test_state = base_state.copy()
    test_state["github_owner"] = "invalid-owner"
    test_state["github_repo"] = "invalid-repo"
    test_state["query"] = "Check repository issues"
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert "github_info" in result_state
    assert "error" in str(result_state["github_info"]).lower()

def test_github_agent_focus_areas(base_state):
    """Test GitHub agent's handling of different focus areas"""
    test_cases = [
        {
            "focus": ["pull_requests"],
            "query": "Review open pull requests",
            "expected_tools": ["fetch_pull_requests"]
        },
        {
            "focus": ["issues"],
            "query": "Check open issues",
            "expected_tools": ["fetch_issues"]
        },
        {
            "focus": ["workflows"],
            "query": "Review GitHub Actions workflows",
            "expected_tools": ["fetch_workflow_runs"]
        },
    ]
    
    for case in test_cases:
        test_state = base_state.copy()
        test_state["github_focus"] = case["focus"]
        test_state["query"] = case["query"]
        
        result_state = github_agent(
            state=test_state,
            model="gpt-4o",
            server="openai"
        )
        
        assert any(tool in str(result_state["github_info"]) 
                  for tool in case["expected_tools"])

def test_github_agent_response_format(base_state):
    """Test that GitHub agent responses are properly formatted"""
    test_state = base_state.copy()
    test_state["query"] = "Get repository information"
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert isinstance(result_state["github_agent_response"], list)
    assert len(result_state["github_agent_response"]) > 0
    assert isinstance(result_state["github_agent_response"][0], SystemMessage)
    
    # Verify response includes metadata sections
    info_text = result_state["github_info"]
    assert "Focus Areas:" in info_text
    assert "Rationale:" in info_text

def test_github_agent_error_handling(base_state, mocker):
    """Test GitHub agent's error handling capabilities"""
    test_state = base_state.copy()
    test_state["query"] = "Check repository status"
    
    # Mock LLM to raise an exception
    mock_llm = mocker.Mock()
    mock_llm.invoke.side_effect = Exception("Simulated LLM error")
    mocker.patch('agents.github_agent.get_open_ai_json', return_value=mock_llm)
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert len(result_state["github_agent_response"]) == 1
    assert "Error in github_agent" in result_state["github_agent_response"][0].content

def test_github_agent_multiple_tools(base_state):
    """Test GitHub agent's handling of requests requiring multiple tools"""
    test_state = base_state.copy()
    test_state["query"] = "Analyze pull requests and their associated workflows"
    test_state["github_focus"] = ["pull_requests", "workflows"]
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    info_text = result_state["github_info"]
    assert "pull_requests" in str(info_text).lower()
    assert "workflow" in str(info_text).lower()

def test_github_agent_empty_focus(base_state):
    """Test GitHub agent's behavior with empty focus areas"""
    test_state = base_state.copy()
    test_state["github_focus"] = []
    test_state["query"] = "Get repository information"
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert "github_info" in result_state
    assert isinstance(result_state["github_info"], str)

def test_github_agent_state_preservation(base_state):
    """Test that GitHub agent preserves existing state fields"""
    test_state = base_state.copy()
    test_state["custom_field"] = "test_value"
    test_state["query"] = "Check repository status"
    
    result_state = github_agent(
        state=test_state,
        model="gpt-4o",
        server="openai"
    )
    
    assert "custom_field" in result_state
    assert result_state["custom_field"] == "test_value"

def test_github_agent_with_complex_queries(base_state):
    """Test GitHub agent's handling of complex multi-part queries"""
    test_cases = [
        {
            "query": """
            1. Check open pull requests
            2. Review associated workflow runs
            3. Analyze deployment status
            """,
            "focus": ["pull_requests", "workflows", "deployments"],
            "expected_tools": ["fetch_pull_requests", "fetch_workflow_runs", "fetch_deployments"]
        },
        {
            "query": """
            - List all branches
            - Show recent commits
            - Check branch protection rules
            """,
            "focus": ["branches", "commits"],
            "expected_tools": ["fetch_branches", "fetch_commits"]
        }
    ]
    
    for case in test_cases:
        test_state = base_state.copy()
        test_state["github_focus"] = case["focus"]
        test_state["query"] = case["query"]
        
        result_state = github_agent(
            state=test_state,
            model="gpt-4o",
            server="openai"
        )
        
        info_text = result_state["github_info"]
        assert all(tool in str(info_text).lower() 
                  for tool in case["expected_tools"])

def test_github_agent_with_special_characters(base_state):
    """Test GitHub agent's handling of queries with special characters"""
    test_cases = [
        {
            "query": "Check PR #123 & issue #456",
            "focus": ["pull_requests", "issues"]
        },
        {
            "query": "Review workflow run [ID: abc-123]",
            "focus": ["workflows"]
        },
        {
            "query": "Analyze commit SHA: a1b2c3d4",
            "focus": ["commits"]
        }
    ]
    
    for case in test_cases:
        test_state = base_state.copy()
        test_state["github_focus"] = case["focus"]
        test_state["query"] = case["query"]
        
        result_state = github_agent(
            state=test_state,
            model="gpt-4o",
            server="openai"
        )
        
        assert "github_info" in result_state
        assert isinstance(result_state["github_info"], str)

def test_github_agent_prompt_quality():
    """Test if the GitHub agent's prompt is well-formed and complete"""
    prompt = github_agent_prompt
    
    essential_terms = [
        "github",
        "repository",
        "tools",
        "focus",
        "analyze"
    ]
    
    for term in essential_terms:
        assert term.lower() in prompt.lower(), \
            f"Prompt missing essential term: {term}"
    
    assert "{" in prompt and "}" in prompt, \
        "Prompt missing format placeholders"

def test_github_agent_response_consistency(base_state):
    """Test GitHub agent's consistency in responses for identical queries"""
    test_query = "Check repository pull requests"
    test_focus = ["pull_requests"]
    num_iterations = 3
    results = []
    
    for _ in range(num_iterations):
        test_state = base_state.copy()
        test_state["query"] = test_query
        test_state["github_focus"] = test_focus
        
        result_state = github_agent(
            state=test_state,
            model="gpt-4o",
            server="openai"
        )
        
        response = result_state["github_agent_response"][0].content
        parsed_response = json.loads(response)
        results.append(parsed_response.get("tools_to_use", []))
    
    # Check consistency in tool selection
    first_result = results[0]
    for result in results[1:]:
        assert set(result) == set(first_result), \
            "Inconsistent tool selection across identical queries"