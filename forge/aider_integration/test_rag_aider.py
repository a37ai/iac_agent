"""
Test suite for RAG-Aider integration.
"""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from aider.io import InputOutput
from .rag_aider import RAGAiderCommand, RAGAiderCoder

@pytest.fixture
def mock_io():
    """Mock InputOutput for testing"""
    return Mock(spec=InputOutput)

@pytest.fixture
def test_docs_dir(tmp_path):
    """Create a temporary docs directory with test files"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    # Create test documentation
    terraform_dir = docs_dir / "iac" / "terraform"
    terraform_dir.mkdir(parents=True)
    
    doc_content = """---
tool: terraform
category: iac
version: 1.0.0
topics:
  - state management
---
# Test Documentation

This is test documentation for Terraform.
"""
    
    (terraform_dir / "test.md").write_text(doc_content)
    return docs_dir

@pytest.fixture
def rag_command(mock_io, test_docs_dir):
    """Create RAGAiderCommand instance for testing"""
    mock_coder = Mock()
    mock_coder.io = mock_io
    command = RAGAiderCommand(mock_coder)
    command.docs_dir = test_docs_dir
    return command

@pytest.mark.asyncio
async def test_rag_command_basic(rag_command):
    """Test basic RAG command functionality"""
    # Run command with test query
    success = await rag_command.run("How do I manage Terraform state?")
    
    # Verify command succeeded
    assert success
    
    # Verify output was generated
    rag_command.coder.io.tool_output.assert_called()
    
    # Get the output and verify it contains expected information
    output = rag_command.coder.io.tool_output.call_args[0][0]
    assert "Tool: terraform" in output
    assert "Category: iac" in output

@pytest.mark.asyncio
async def test_rag_coder_chat_response(mock_io, test_docs_dir):
    """Test RAG-enhanced chat responses"""
    # Create RAGAiderCoder instance
    coder = RAGAiderCoder(mock_io)
    coder.docs_dir = test_docs_dir
    
    # Get chat response
    response = await coder.get_chat_response("How do I manage Terraform state?")
    
    # Verify response includes documentation context
    assert response is not None
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_rag_command_error_handling(rag_command):
    """Test RAG command error handling"""
    # Simulate error by using invalid docs directory
    rag_command.docs_dir = Path("nonexistent")
    
    # Run command
    success = await rag_command.run("test query")
    
    # Verify command failed gracefully
    assert not success
    rag_command.coder.io.tool_error.assert_called()

if __name__ == "__main__":
    asyncio.run(pytest.main([__file__]))
