import pytest
import os
from pathlib import Path
from typing import Dict, Any
from states.state import AgentGraphState, PlanStep, LLMDecision
from agents.devops_agents import get_next_devops_action, execute_tool
from agent_tools.devops_tools import DevOpsTools
from forge.forge_wrapper import ForgeWrapper
from utils.subprocess_handler import SubprocessHandler
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

@pytest.fixture
def base_state():
    """Create base state for testing."""
    repo_path = Path(__file__).parent.parent / "test_repos"
    
    state = {
        "query": "Set up basic CI pipeline",
        "repo_path": str(repo_path),
        "current_directory": str(repo_path),
        "plan_steps": [
            PlanStep(
                description="Create GitHub Actions workflow file",
                content="Create a basic CI workflow file",
                step_type="file_creation",
                files=[".github/workflows/ci.yml"]
            )
        ],
        "current_step_index": 0,
        "completed_steps": [],
        "knowledge_sequence": [],
        "current_step_attempts": 0,
        "current_step_context": {},
        "total_attempts": 0,
        "devops_agent_response": [],
        "subprocess_handler": SubprocessHandler(repo_path),
        "forge": ForgeWrapper(git_root=str(repo_path)),
        "tools": None
    }
    
    tools = DevOpsTools(
        working_directory=state["current_directory"],
        subprocess_handler=state["subprocess_handler"]
    )
    tools.set_forge(state["forge"])
    state["tools"] = tools
    
    return state

# def test_execute_command(base_state):
#     """Test execute_command tool."""
#     decision = LLMDecision(
#         type="execute_command",
#         description="List directory contents",
#         content="ls -la",
#         reasoning="Need to check current directory contents"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert len(result_state["knowledge_sequence"]) > 0
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "execute_command"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_execute_command_timeout(base_state):
#     """Test command execution timeout after 20 seconds."""
#     decision = LLMDecision(
#         type="execute_command",
#         description="Run a long-running command",
#         content="sleep 25",  # Command that will run longer than timeout
#         reasoning="Testing timeout handling"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "execute_command"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "error"
#     assert "Command timed out after 20 seconds" in result_state["knowledge_sequence"][-1]["result"]["error"]

# def test_execute_command_with_user_input_1(monkeypatch, base_state):
#     """Test command execution with multiple user inputs."""
#     # Mock user inputs
#     inputs = iter(['yes\n', 'test input\n', 'exit\n'])
#     monkeypatch.setattr('builtins.input', lambda prompt='': next(inputs))
    
#     # Using Python script that explicitly flushes output
#     command = '''python3 -c "
# import sys
# while True:
#     sys.stdout.write('Enter input: ')
#     sys.stdout.flush()
#     line = input()
#     if line == 'exit':
#         break
#     print(f'You entered: {line}')"
# '''
    
#     decision = LLMDecision(
#         type="execute_command",
#         description="Run interactive command",
#         content=command,
#         reasoning="Testing interactive input handling"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "execute_command"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"
#     assert "You entered: yes" in result_state["knowledge_sequence"][-1]["result"]["output"]
#     assert "You entered: test input" in result_state["knowledge_sequence"][-1]["result"]["output"]

# def test_execute_command_with_user_input(monkeypatch, base_state):
#     """Test command execution with user input."""
#     inputs = iter(['hello', 'quit'])
#     monkeypatch.setattr('builtins.input', lambda prompt='': next(inputs))
    
#     # bc calculator command - exits on 'quit'
#     command = "bc"
    
#     decision = LLMDecision(
#         type="execute_command",
#         description="Test input handling",
#         content=command,
#         reasoning="Testing interactive input"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "execute_command"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

def test_execute_terraform_command(monkeypatch, base_state):
    """Test terraform init command execution."""
    import subprocess
    
    # First run terraform init directly to see the output
    init_output = subprocess.run(
        "terraform init",
        shell=True,
        cwd=base_state["current_directory"],
        capture_output=True,
        text=True
    )
    print(f"Debug - Terraform Output:\n{init_output.stdout}")
    
    inputs = iter([
        'yes\n', 'yes\n', 'yes\n', 'yes\n', 'yes\n',  # More inputs for redundancy
        'exit\n'  # Emergency exit
    ])
    monkeypatch.setattr('builtins.input', lambda prompt='': next(inputs))

    decision = LLMDecision(
        type="execute_command",
        description="Run terraform init",
        content="terraform init",
        reasoning="Testing terraform init"
    )
    
    base_state["current_step_context"]["last_decision"] = decision.dict()
    result_state = execute_tool(base_state)
    
    print(f"Debug - Result:\n{result_state['knowledge_sequence'][-1]['result']}")
    
    assert result_state["knowledge_sequence"][-1]["action_type"] == "execute_command"
    assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_execute_command_with_environment_vars(base_state):
#     """Test command execution with environment variables."""
#     import os
#     os.environ["TEST_VAR"] = "test_value"
    
#     decision = LLMDecision(
#         type="execute_command",
#         description="Echo environment variable",
#         content="echo $TEST_VAR",
#         reasoning="Testing environment variable handling"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"
#     assert "test_value" in result_state["knowledge_sequence"][-1]["result"]["output"]

# def test_execute_command_with_pipes(base_state):
#     """Test command execution with pipe operations."""
#     # Create a test file
#     test_file = Path(base_state["current_directory"]) / "test_file.txt"
#     test_file.write_text("line1\nline2\nline3\nline4\nline5")
    
#     decision = LLMDecision(
#         type="execute_command",
#         description="Test pipe operations",
#         content="cat test_file.txt | grep line | wc -l",
#         reasoning="Testing complex command with pipes"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"
#     assert "5" in result_state["knowledge_sequence"][-1]["result"]["output"]

# def test_create_file(base_state):
#     """Test file creation tool."""
#     decision = LLMDecision(
#         type="create_file",
#         description="""def test():
#     print("test")""",
#         content="test.py",
#         reasoning="Creating test file"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert len(result_state["knowledge_sequence"]) > 0
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "create_file"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"
#     assert Path(base_state["current_directory"]).joinpath("test.py").exists()

# def test_modify_code(base_state):
#     """Test code modification tool."""
#     # First create a file
#     test_file = Path(base_state["current_directory"]) / "test.py"
#     test_file.write_text("def hello():\n    print('Hello')")
    
#     decision = LLMDecision(
#         type="modify_code",
#         description="Add world parameter",
#         content="def hello(world='World'):\n    print(f'Hello {world}')",
#         reasoning="Adding parameter support"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert len(result_state["knowledge_sequence"]) > 0
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "modify_code"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_validate_code_changes(base_state):
#     """Test code validation tool."""
#     test_file = Path(base_state["current_directory"]) / "app.py"
#     test_file.write_text("def add(a, b):\n    return a + b")
    
#     decision = LLMDecision(
#         type="validate_code_changes",
#         description="Add type hints",
#         content="def add(a: int, b: int) -> int:\n    return a + b",
#         reasoning="Adding type hints for better code quality"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "validate_code_changes"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_validate_command_output(base_state):
#     """Test command output validation."""
#     decision = LLMDecision(
#         type="validate_command_output",
#         description="Directory should contain test file",
#         content="ls -la | grep test",
#         reasoning="Verifying test file creation"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "validate_command_output"

# def test_run_file(base_state):
#     """Test file execution tool."""
#     script_file = Path(base_state["current_directory"]).joinpath("test_script.py")
#     script_file.write_text('print("Hello from test script")')
#     script_file.chmod(0o755)  # Add execute permissions
    
#     decision = LLMDecision(
#         type="run_file",
#         description="Execute test script",
#         content="test_script.py",
#         reasoning="Testing script execution"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "run_file"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_delete_file(base_state):
#     """Test file deletion tool."""
#     test_file = Path(base_state["current_directory"]) / "to_delete.txt"
#     test_file.write_text("Test content")
    
#     decision = LLMDecision(
#         type="delete_file",
#         description="Remove temporary file",
#         content="to_delete.txt",
#         reasoning="Cleanup"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "delete_file"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"
#     assert not test_file.exists()

# def test_get_next_devops_action_basic(base_state):
#     """Test basic decision making."""
#     # Add required fields for LLM context
#     base_state["codebase_overview"] = "Test repository"
#     base_state["file_tree"] = {"src": {"main.py": "file"}}
#     base_state["file_analyses"] = {}

#     result_state = get_next_devops_action(
#         state=base_state,
#         model="gpt-4o",
#         server="openai"
#     )
    
#     assert "current_step_context" in result_state
#     assert "last_decision" in result_state["current_step_context"]

# def test_get_next_devops_action_with_ci_setup(base_state):
#     """Test CI pipeline setup decisions."""
#     base_state["codebase_overview"] = "Python project requiring CI"
#     base_state["file_tree"] = {"src": {"main.py": "file"}}
#     base_state["file_analyses"] = {}
#     base_state["plan_steps"] = [
#         PlanStep(
#             description="Set up GitHub Actions CI pipeline",
#             content="Create a basic CI pipeline",
#             step_type="ci_setup",
#             files=[".github/workflows/python-ci.yml"]
#         )
#     ]
    
#     result_state = get_next_devops_action(
#         state=base_state,
#         model="gpt-4o",
#         server="openai"
#     )
    
#     decision = LLMDecision(**result_state["current_step_context"]["last_decision"])
#     assert decision.type in ["create_file", "modify_code"]


# def test_complex_workflow(base_state):
#     """Test multi-step workflow."""
#     test_dir = Path(base_state["current_directory"])
#     base_state["codebase_overview"] = "Python project setup"
#     base_state["file_tree"] = {"src": {}, "tests": {}}
#     base_state["file_analyses"] = {}
    
#     (test_dir / "src").mkdir(exist_ok=True)
#     (test_dir / "tests").mkdir(exist_ok=True)
#     (test_dir / "src" / "main.py").write_text("def main():\n    pass")

#     base_state["plan_steps"] = [
#         PlanStep(
#             description="Create package structure",
#             content="Set up Python project layout",
#             step_type="setup",
#             files=["setup.py"]
#         )
#     ]
    
#     result_state = get_next_devops_action(
#         state=base_state,
#         model="gpt-4o",
#         server="openai"
#     )
    
#     assert "last_decision" in result_state["current_step_context"]

# def test_error_handling(base_state):
#     """Test handling of errors during execution."""
#     # Create invalid decision
#     decision = LLMDecision(
#         type="execute_command",
#         description="Run invalid command",
#         content="invalidcommand --flag",
#         reasoning="Testing error handling"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "error"
#     assert result_state["current_step_attempts"] == 1

# def test_file_validation_workflow(base_state):
#     """Test file validation workflow."""
#     test_path = Path(base_state["current_directory"])
#     requirements_path = test_path / "requirements.txt"
#     requirements_path.write_text("python>=3.8\npytest\nrequests")
    
#     decision = LLMDecision(
#         type="validate_file_output",
#         description="File should contain standard Python package requirements",
#         content=requirements_path.read_text(),
#         reasoning="Validating requirements format"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "validate_file_output"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_multi_file_changes(base_state):
#     """Test handling multiple file changes in sequence."""
#     (Path(base_state["current_directory"]) / "src").mkdir(exist_ok=True)
    
#     files = {
#         "src/config.py": "CONFIG = {'env': 'dev'}",
#         "src/main.py": "from config import CONFIG\n\ndef main():\n    print(CONFIG)",
#         "src/utils.py": "def helper():\n    pass"
#     }
    
#     for path, content in files.items():
#         file_path = Path(base_state["current_directory"]) / path
#         file_path.write_text(content)
    
#     base_state["plan_steps"][0].files = list(files.keys())
    
#     decision = LLMDecision(
#         type="modify_code",
#         description="Update configuration handling",
#         content="import os\n\nCONFIG = {\n    'env': os.getenv('ENV', 'dev')\n}",
#         reasoning="Adding environment variable support"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_step_completion(base_state):
#     """Test proper completion of steps."""
#     gitignore_path = Path(base_state["current_directory"]) / ".gitignore"
#     gitignore_path.write_text("*.pyc\n__pycache__/")

#     base_state["codebase_overview"] = "Test repository"
#     base_state["file_tree"] = {".gitignore": "file"}
#     base_state["file_analyses"] = {}
#     base_state["current_step_index"] = 0
#     base_state.update({
#         "credentials": {},
#         "subprocess_handler": SubprocessHandler(base_state["current_directory"]),
#         "knowledge_sequence": []
#     })
#     base_state["plan_steps"] = [
#         PlanStep(
#             description="Initialize git repository",
#             content="Set up git repo with initial commit",
#             step_type="setup",
#             files=[".gitignore"]
#         ),
#         PlanStep(
#             description="Create README",
#             content="Add project documentation",
#             step_type="documentation",
#             files=["README.md"]
#         )
#     ]

#     decision = LLMDecision(
#         type="end",
#         description="Step completed successfully",
#         content="",
#         reasoning="All tasks for current step finished"
#     )

#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = get_next_devops_action(base_state, model="gpt-4o", server="openai")
    
#     assert result_state["current_step_index"] == 1

# def test_human_interaction(base_state):
#     """Test tools requiring human interaction."""
#     decision = LLMDecision(
#         type="ask_human_for_information",
#         description="Get database credentials",
#         content="What is the database connection string?",
#         reasoning="Need database access information"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert "ask_human_for_information" in result_state["knowledge_sequence"][-1]["action_type"]

# def test_retrieve_documentation(base_state):
#     """Test documentation retrieval."""
#     if not os.getenv("PERPLEXITY_API_KEY"):
#         pytest.skip("Perplexity API token not available")
        
#     decision = LLMDecision(
#         type="retrieve_documentation",  
#         description="Fetch documentation",
#         content="python setuptools configuration",
#         reasoning="Need package setup reference"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "retrieve_documentation"

# def test_copy_template(base_state):
#     """Test template copying."""
#     template_dir = Path(base_state["current_directory"]) / "templates"
#     template_dir.mkdir(parents=True, exist_ok=True)
#     template_file = template_dir / "app_template.py"
#     template_file.write_text("APP_NAME = '{{app_name}}'\nPORT = {{port}}")
    
#     decision = LLMDecision(
#         type="copy_template",
#         description="Customize app template",
#         content=str(template_file),  # Use absolute path
#         reasoning="Setting up new app"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "copy_template"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"

# def test_ask_human_for_intervention(base_state):
#     """Test human intervention request tool."""
#     decision = LLMDecision(
#         type="ask_human_for_intervention",
#         description="Manual deployment check needed",
#         content="Please verify the staging deployment is working as expected",
#         reasoning="Need human verification of deployment"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "ask_human_for_intervention"

# def test_validate_output(base_state):
#     """Test output validation with LLM."""
#     test_output = "Configuration successful"
    
#     decision = LLMDecision(
#         type="validate_command_output", # Changed from validate_output
#         description="Configuration should complete without errors",
#         content=test_output,
#         reasoning="Verifying configuration"
#     )
    
#     base_state["current_step_context"]["last_decision"] = decision.dict()
#     result_state = execute_tool(base_state)
    
#     assert result_state["knowledge_sequence"][-1]["action_type"] == "validate_command_output"
#     assert result_state["knowledge_sequence"][-1]["result"]["status"] == "success"
