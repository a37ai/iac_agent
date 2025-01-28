import pytest
import json
import os
from pathlib import Path
from datetime import datetime
from langchain_core.messages import SystemMessage
from agents.system_mapper_agents import system_mapper_agent
from agent_tools.system_mapper_tools import SystemMapper
from agent_tools.memory_tools import MemoryTools
from states.state import Memory

@pytest.fixture
def base_state():
    """Create base state fixture with minimal required fields."""
    return {
        "repo_path": str(Path.cwd() / "test_repos"),
        "codebase_overview": "",
        "file_tree": {},
        "file_analyses": {},
        "system_mapper_response": [],
        "repo_type": "mono",
        "memory_context": None
    }

@pytest.fixture
def mock_repo(tmp_path):
    """Create a mock repository structure."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Create standard structure
    (repo_dir / "src").mkdir()
    (repo_dir / "tests").mkdir()
    (repo_dir / "config").mkdir()
    
    # Add sample files
    (repo_dir / "src/main.py").write_text("def main(): pass")
    (repo_dir / "tests/test_main.py").write_text("def test_main(): pass")
    (repo_dir / "config/config.yaml").write_text("env: development")
    
    return repo_dir

def test_basic_mapping(base_state, mock_repo, monkeypatch):
    """Test basic system mapping functionality."""
    # Setup
    test_state = base_state.copy()
    test_state["repo_path"] = str(mock_repo)
    monkeypatch.setenv("REPO_URLS", "")
    
    # Execute
    result_state = system_mapper_agent(test_state)
    
    # Verify
    assert "codebase_overview" in result_state
    assert isinstance(result_state["file_tree"], dict)
    assert isinstance(result_state["file_analyses"], dict)
    assert len(result_state["system_mapper_response"]) > 0
    assert isinstance(result_state["system_mapper_response"][0], SystemMessage)
    assert "System mapping complete" in result_state["system_mapper_response"][0].content

def test_memory_storage(base_state, mock_repo, monkeypatch, mocker):
    """Test memory storage functionality."""
    # Setup
    test_state = base_state.copy()
    test_state["repo_path"] = str(mock_repo)
    monkeypatch.setenv("REPO_URLS", "https://github.com/test/repo.git")
    
    # Mock SystemMapper and MemoryTools
    mock_system_map = {
        "repository_overview": "Test overview",
        "file_tree": {"test.py": "file"},
        "file_analyses": {"test.py": {"purpose": "test"}}
    }
    mock_mapper = mocker.Mock(spec=SystemMapper)
    mock_mapper.generate_system_map.return_value = mock_system_map
    mocker.patch('agents.system_mapper_agents.SystemMapper', return_value=mock_mapper)
    
    mock_memory_tools = mocker.Mock(spec=MemoryTools)
    mocker.patch('agents.system_mapper_agents.MemoryTools', return_value=mock_memory_tools)
    
    # Execute
    result_state = system_mapper_agent(test_state)
    
    # Verify
    assert mock_memory_tools.store_memories.called
    stored_memories = mock_memory_tools.store_memories.call_args[0][0]
    assert isinstance(stored_memories, list)
    assert all(isinstance(memory, Memory) for memory in stored_memories)
    assert len(stored_memories) == 2  # One for overview, one for file analysis

def test_error_handling(base_state, mocker):
    """Test error handling in system mapper."""
    # Setup
    test_state = base_state.copy()
    mock_mapper = mocker.Mock(spec=SystemMapper)
    mock_mapper.generate_system_map.side_effect = Exception("Test error")
    mocker.patch('agents.system_mapper_agents.SystemMapper', return_value=mock_mapper)
    
    # Execute
    result_state = system_mapper_agent(test_state)
    
    # Verify
    assert len(result_state["system_mapper_response"]) > 0
    assert "Error in system_mapper_agent" in result_state["system_mapper_response"][0].content
    assert "Test error" in result_state["system_mapper_response"][0].content

def test_existing_memory_context(base_state, mock_repo, monkeypatch, mocker):
    """Test handling of existing memory context."""
    # Setup
    test_state = base_state.copy()
    test_state["repo_path"] = str(mock_repo)
    test_state["memory_context"] = mocker.Mock(
        past_analyses={"test": "analysis"},
        past_overview="test overview"
    )
    monkeypatch.setenv("REPO_URLS", "https://github.com/test/repo.git")
    
    # Mock MemoryTools
    mock_memory_tools = mocker.Mock(spec=MemoryTools)
    mocker.patch('agents.system_mapper_agents.MemoryTools', return_value=mock_memory_tools)
    
    # Execute
    result_state = system_mapper_agent(test_state)
    
    # Verify
    assert not mock_memory_tools.store_memories.called

def test_file_analysis_content(base_state, mock_repo, monkeypatch, mocker):
    """Test content of file analyses."""
    # Setup
    test_state = base_state.copy()
    test_state["repo_path"] = str(mock_repo)
    monkeypatch.setenv("REPO_URLS", "")
    
    # Add test file with specific content
    test_file = mock_repo / "src/test_file.py"
    test_file.write_text("""
    import os
    import json
    
    def process_data(data):
        '''Process input data'''
        return json.dumps(data)
    """)
    
    # Mock SystemMapper with test file analysis
    mock_system_map = {
        "repository_overview": "Test overview",
        "file_tree": {str(test_file): "file"},
        "file_analyses": {
            str(test_file): {
                "main_purpose": "Process data using JSON",
                "key_components": ["process_data"],
                "dependencies": ["os", "json"],
                "patterns": []
            }
        }
    }
    mock_mapper = mocker.Mock(spec=SystemMapper)
    mock_mapper.generate_system_map.return_value = mock_system_map
    mocker.patch('agents.system_mapper_agents.SystemMapper', return_value=mock_mapper)
    
    # Execute
    result_state = system_mapper_agent(test_state)
    
    # Verify
    analyses = result_state["file_analyses"]
    assert any("test_file.py" in path for path in analyses.keys())
    analysis = next(v for k, v in analyses.items() if "test_file.py" in k)
    assert "json" in analysis["dependencies"]

def test_excluded_patterns(base_state, mock_repo, monkeypatch):
    """Test exclusion of specific patterns and directories."""
    # Setup
    test_state = base_state.copy()
    test_state["repo_path"] = str(mock_repo)
    monkeypatch.setenv("REPO_URLS", "")
    
    # Create excluded directories and files
    (mock_repo / "__pycache__").mkdir()
    (mock_repo / ".git").mkdir()
    (mock_repo / ".env").write_text("SECRET=value")
    
    # Execute
    result_state = system_mapper_agent(test_state)
    
    # Verify
    file_tree_str = str(result_state["file_tree"])
    assert "__pycache__" not in file_tree_str
    assert ".git" not in file_tree_str
    assert ".env" not in file_tree_str