"""DevOps tools implementation using LLM-based validations (via langgraph)."""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import subprocess
import os
import shutil
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import json

# LangChain / LLM imports for direct comparison
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# Load environment variables
load_dotenv()

class ToolResult(BaseModel):
    """Structure for tool execution results."""
    status: str  # "success" or "error"
    output: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "error": self.error
        }

class DevOpsTools:
    """Collection of tools for DevOps automation, including code execution and LLM-based validations."""
    
    def __init__(self, working_directory: str, subprocess_handler: Any):
        self.working_directory = Path(working_directory)
        self.subprocess_handler = subprocess_handler
        self.forge = None
        
        # Make sure the working directory exists
        self.working_directory.mkdir(parents=True, exist_ok=True)
    
    def set_forge(self, forge: Any):
        """Set the Forge instance for code execution."""
        self.forge = forge
    
    ########################################################################
    #  Simple command and code execution
    ########################################################################
    
    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """Execute a shell command in a subprocess."""
        try:
            effective_cwd = cwd if cwd else str(self.working_directory)
            result = self.subprocess_handler.execute_command(
                command,
                timeout=timeout if timeout else 300
            )
            if result['status'] == 'success':
                return ToolResult(status="success", output=result['stdout'])
            else:
                return ToolResult(status="error", error=result['stderr'])
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def modify_code(self, code: str, instructions: str, cwd: Optional[str] = None) -> ToolResult:
        """Execute code through Forge's chat interface, returning a ToolResult."""
        if self.forge is None:
            return ToolResult(
                status="error",
                error="Forge not initialized"
            )
        try:
            effective_cwd = Path(cwd if cwd else str(self.working_directory)).resolve()
            os.chdir(effective_cwd)
            
            message = f"""Please execute the following specification to these instructions:

Instructions: {instructions}

Code:

python
{code}

Please make any necessary modifications and execute the code.
"""
            forge_response = self.forge.chat_and_get_updates(message)
            
            # Wrap the forge response in a ToolResult
            if isinstance(forge_response, dict):
                # If there's an error indicated
                if forge_response.get("status") == "error":
                    return ToolResult(
                        status="error",
                        error=forge_response.get("error", "Unknown error")
                    )
                # Otherwise assume success
                return ToolResult(
                    status="success",
                    output=json.dumps(forge_response, indent=2)
                )
            else:
                # If not a dict, just return success with stringified response
                return ToolResult(
                    status="success",
                    output=str(forge_response)
                )
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error executing code through Forge: {str(e)}"
            )

    ########################################################################
    #  File I/O
    ########################################################################
    
    def delete_file(self, file_path: str, cwd: Optional[str] = None) -> ToolResult:
        """Remove a file if it exists."""
        try:
            effective_cwd = Path(cwd if cwd else str(self.working_directory)).resolve()
            full_path = Path(os.path.join(effective_cwd, file_path)).resolve()
            if not full_path.exists():
                return ToolResult(status="error", error=f"File not found: {file_path}")
            full_path.unlink()
            return ToolResult(status="success", output=f"Deleted file: {file_path}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def create_file(
        self,
        file_path: str,
        content: str,
        mode: Optional[int] = None,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """Create or overwrite a file with the given content."""
        try:
            effective_cwd = Path(cwd if cwd else str(self.working_directory)).resolve()
            full_path = Path(os.path.join(effective_cwd, file_path)).resolve()
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if mode is not None:
                full_path.chmod(mode)
            
            return ToolResult(status="success", output=f"Created file: {file_path}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def copy_template(
        self,
        template_path: str,
        destination_path: Optional[str] = None,
        replacements: Optional[Dict[str, str]] = None
    ) -> ToolResult:
        """Copy a file or directory from a template, optionally performing text replacements."""
        try:
            template_path = Path(template_path).resolve()
            dest = Path(destination_path if destination_path else str(self.working_directory)).resolve()
            if not template_path.exists():
                return ToolResult(status="error", error=f"Template not found: {template_path}")
            
            if template_path.is_file():
                shutil.copy2(template_path, dest)
                copied_files = [os.path.join(dest, template_path.name)]
            else:
                shutil.copytree(template_path, dest, dirs_exist_ok=True)
                copied_files = []
                for root, _, files in os.walk(dest):
                    for file in files:
                        copied_files.append(os.path.join(root, file))
            
            if replacements:
                for path_ in copied_files:
                    if os.path.isfile(path_):
                        with open(path_, 'r', encoding='utf-8') as f:
                            content = f.read()
                        for old, new in replacements.items():
                            content = content.replace(old, new)
                        with open(path_, 'w', encoding='utf-8') as f:
                            f.write(content)
            
            return ToolResult(status="success", output=f"Copied template to {dest}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def run_file(
        self,
        file_path: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """Execute a file directly (like a script)."""
        try:
            effective_cwd = Path(cwd if cwd else str(self.working_directory)).resolve()
            full_path = Path(os.path.join(effective_cwd, file_path)).resolve()
            if not full_path.exists():
                return ToolResult(status="error", error=f"File not found: {file_path}")
            
            cmd = [str(full_path)]
            if args:
                cmd.extend(args)
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(effective_cwd))
            return ToolResult(status="success", output=result.stdout)
        except subprocess.CalledProcessError as e:
            return ToolResult(status="error", error=f"Process error: {e.stderr}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
        
    ########################################################################
    #  Human involvement
    ########################################################################
    
    def ask_human(self, question: str) -> ToolResult:
        """Prompt the user for input via console (blocking)."""
        try:
            print(f"\n[DEVOPS AGENT QUESTION]: {question}")
            print(f"[INFO] Working Directory: {self.working_directory}")
            answer = input("Your response: ").strip()
            return ToolResult(status="success", output=answer)
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    ########################################################################
    #  LLM-based validations (via langchain_openai + custom prompts)
    ########################################################################
    
    def _llm_validation_check(self, prompt_text: str) -> ToolResult:
        """
        Helper: Use an LLM (via langgraph + langchain_openai) to compare two texts
        or otherwise validate correctness. Expect a JSON with "valid": "YES"/"NO" 
        and an "explanation".
        """
        try:
            llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
            
            # We will instruct the LLM to respond strictly in JSON:
            template = """You are a helpful AI that must analyze the given context 
and produce a strict JSON response in the format:
{{
  "valid": "YES" or "NO",
  "explanation": "string explaining why"
}}

Context to analyze:
{context}
"""
            prompt = PromptTemplate(
                template=template,
                input_variables=["context"]
            )
            response = llm.invoke(prompt.format(context=prompt_text))
            
            # Parse the JSON output
            data = json.loads(response.content.strip())
            valid = data.get("valid", "").upper()
            explanation = data.get("explanation", "No explanation provided.")
            
            if valid == "YES":
                return ToolResult(status="success", output=explanation)
            else:
                return ToolResult(status="error", error=explanation)
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"LLM validation failed: {str(e)}"
            )

    def validate_command_output(self, command_output: str, expected_behavior: str) -> ToolResult:
        """
        Use an LLM to compare the actual command output to an expected behavior.
        Return 'success' if it matches, else 'error'.
        """
        prompt_text = f"""Compare the actual command output to an expected behavior.

Expected:
{expected_behavior}

Actual:
{command_output}

        Return 'success' if it matches, else 'error'.

"""
        return self._llm_validation_check(prompt_text)
    
    def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> ToolResult:
        """
        Use an LLM to compare the actual code changes to the expected changes.
        Return 'success' if it matches, else 'error'.
        """
        prompt_text = f"""We have code changes and an expected set of changes.
Instructions that were followed: {instructions}

Expected changes:
{expected_changes}

Actual code changes:
{code}

        Return 'success' if it matches, else 'error'.

"""
        return self._llm_validation_check(prompt_text)
    
    def validate_file_output(self, file_content: str, expected_content: str) -> ToolResult:
        """
        Use an LLM to compare the actual file content to the expected content.
        Return 'success' if it matches, else 'error'.
        """
        prompt_text = f"""Compare the actual file content to the expected content.

Expected:
{expected_content}

Actual:
{file_content}

        Return 'success' if it matches, else 'error'.

"""
        return self._llm_validation_check(prompt_text)
