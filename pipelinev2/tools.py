"""DevOps tools implementation without logging library usage."""
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

# Load environment variables
load_dotenv()

class ToolResult(BaseModel):
    """Structure for tool execution results"""
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
    """Collection of tools for DevOps automation."""
    
    def __init__(self, working_directory: str, subprocess_handler: Any):
        self.working_directory = Path(working_directory)
        self.subprocess_handler = subprocess_handler
        self.forge = None
        self.perplexity_token = os.getenv('PERPLEXITY_API_TOKEN')
        
        # Ensure working directory exists
        self.working_directory.mkdir(parents=True, exist_ok=True)
        
    def set_forge(self, forge: Any):
        """Set the Forge instance for code execution."""
        self.forge = forge
    
    def retrieve_documentation(self, query: str, domain_filter: Optional[List[str]] = None) -> ToolResult:
        """Retrieve documentation using Perplexity API."""
        if not self.perplexity_token:
            return ToolResult(
                status="error",
                error="PERPLEXITY_API_TOKEN not set in environment"
            )
        try:
            url = "https://api.perplexity.ai/chat/completions"
            
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a technical documentation expert. "
                            "Provide clear, accurate, and relevant information."
                        )
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "temperature": 0.2,
                "top_p": 0.9,
                "search_domain_filter": domain_filter if domain_filter else [],
                "return_images": False,
                "return_related_questions": False,
                "search_recency_filter": "month",
                "frequency_penalty": 1
            }
            
            headers = {
                "Authorization": f"Bearer {self.perplexity_token}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            citations = result.get("citations", [])
            
            output = f"{content}\n\nSources:\n"
            for citation in citations:
                output += f"- {citation['url']}\n"
            
            return ToolResult(status="success", output=output)
        
        except requests.exceptions.RequestException as e:
            return ToolResult(
                status="error",
                error=f"API request failed: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error retrieving documentation: {str(e)}"
            )
    
    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """Execute a shell command with pattern matching (if needed)."""
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
    

    def execute_code(self, code: str, instructions: str, cwd: Optional[str] = None) -> ToolResult:
        """Execute code through Forge's chat interface."""
        if self.forge is None:
            return ToolResult(
                status="error",
                error="Forge not initialized"
            )
            
        try:
            effective_cwd = cwd if cwd else str(self.working_directory)
            os.chdir(effective_cwd)
            
            # Format the message for Forge
            message = f"""Please execute the following specification to these instructions.

                    Instructions: {instructions}

                    Code:
                    ```python
                    {code}
                    ```

                    Please make any necessary modifications and execute the code."""
            
            return self.forge.chat_and_get_updates(message)
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error executing code through Forge: {str(e)}"
            )

    def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> ToolResult:
        """Validate code changes using Forge's chat capabilities."""
        if self.forge is None:
            return ToolResult(
                status="error",
                error="Forge not initialized"
            )
            
        try:
            message = f"""Please validate the following code changes:

Expected Changes:
{expected_changes}

Actual Code:
```python
{code}
```

Instructions that were followed:
{instructions}

Please analyze if the code changes match the expected changes and respond with:
1. Whether the changes match (YES/NO)
2. A brief explanation of why
3. Any potential issues or improvements needed"""

            return self.forge_chat(message)
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error validating code changes: {str(e)}"
            )

    def validate_file_output(self, file_content: str, expected_content: str) -> ToolResult:
        """Validate file contents using Forge's chat capabilities."""
        if self.forge is None:
            return ToolResult(
                status="error",
                error="Forge not initialized"
            )
            
        try:
            message = f"""Please validate the following file contents:

Expected Content:
```
{expected_content}
```

Actual Content:
```
{file_content}
```

Please analyze if the actual content matches the expected content and respond with:
1. Whether they match (YES/NO)
2. A brief explanation of why
3. Any discrepancies found"""

            return self.forge_chat(message)
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error validating file output: {str(e)}"
            )
    
    def ask_human(self, question: str) -> ToolResult:
        """Prompt the user for input via console."""
        try:
            print(f"\n[DEVOPS AGENT QUESTION]: {question}")
            print(f"[INFO] Working Directory: {self.working_directory}")
            answer = input("Your response: ").strip()
            return ToolResult(status="success", output=answer)
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def run_file(
        self,
        file_path: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """Execute a file directly."""
        try:
            effective_cwd = cwd if cwd else str(self.working_directory)
            full_path = os.path.join(effective_cwd, file_path)
            if not os.path.exists(full_path):
                return ToolResult(status="error", error=f"File not found: {file_path}")
            
            cmd = [full_path]
            if args:
                cmd.extend(args)
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=effective_cwd)
            return ToolResult(status="success", output=result.stdout)
        except subprocess.CalledProcessError as e:
            return ToolResult(status="error", error=f"Process error: {e.stderr}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def validate_output(
        self,
        output: str,
        expected_behavior: str,
        validation_criteria: List[str]
    ) -> ToolResult:
        """Check command output against a list of criteria by simple substring checks."""
        try:
            failed = []
            for criterion in validation_criteria:
                if criterion.lower() not in output.lower():
                    failed.append(criterion)
            if failed:
                return ToolResult(
                    status="error",
                    error="Failed validation: " + ", ".join(failed)
                )
            return ToolResult(status="success", output="All criteria met.")
        except Exception as e:
            return ToolResult(status="error", error=str(e))

    # --- LLM-based validations (via retrieve_documentation) ---
    def validate_command_output(self, command_output: str, expected_behavior: str) -> ToolResult:
        prompt = f"""
Compare the actual output to the expected behavior.

Expected Behavior:
{expected_behavior}

Actual Output:
{command_output}

Do they match? Return "YES" or "NO" plus explanation.
"""
        try:
            return self.retrieve_documentation(prompt)
        except Exception as e:
            return ToolResult(status="error", error=f"Validation failed: {e}")
    
    def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> ToolResult:
        prompt = f"""
Compare the actual code changes to the expected changes.

Expected Changes:
{expected_changes}

Actual Code:
{code}
Instructions: {instructions}

Respond with "YES" if it matches, else "NO" plus short explanation.
"""
        try:
            return self.retrieve_documentation(prompt)
        except Exception as e:
            return ToolResult(status="error", error=f"Validation failed: {e}")
    
    def validate_file_output(self, file_content: str, expected_content: str) -> ToolResult:
        prompt = f"""
Compare the actual file content to the expected content.

Expected Content:
{expected_content}

Actual Content:
{file_content}

Respond with "YES" if it matches, else "NO" plus short explanation.
"""
        try:
            return self.retrieve_documentation(prompt)
        except Exception as e:
            return ToolResult(status="error", error=f"Validation failed: {e}")
    # --- End LLM-based validations ---
    
    def delete_file(self, file_path: str, cwd: Optional[str] = None) -> ToolResult:
        """Remove a file if it exists."""
        try:
            effective_cwd = cwd if cwd else str(self.working_directory)
            full_path = os.path.join(effective_cwd, file_path)
            if not os.path.exists(full_path):
                return ToolResult(status="error", error=f"File not found: {file_path}")
            os.remove(full_path)
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
        """Create or overwrite a file with given content."""
        try:
            effective_cwd = cwd if cwd else str(self.working_directory)
            full_path = os.path.join(effective_cwd, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            if mode is not None:
                os.chmod(full_path, mode)
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
            dest = destination_path if destination_path else str(self.working_directory)
            if not os.path.exists(template_path):
                return ToolResult(status="error", error=f"Template not found: {template_path}")
            
            if os.path.isfile(template_path):
                shutil.copy2(template_path, dest)
                template_files = [os.path.join(dest, os.path.basename(template_path))]
            else:
                shutil.copytree(template_path, dest, dirs_exist_ok=True)
                template_files = []
                for root, _, files in os.walk(dest):
                    for file in files:
                        template_files.append(os.path.join(root, file))
            
            if replacements:
                for file_path in template_files:
                    if os.path.isfile(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        for old, new in replacements.items():
                            content = content.replace(old, new)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
            
            return ToolResult(status="success", output=f"Copied template to {dest}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    def validate_forge_changes(self, files: List[str], expected_changes: str) -> ToolResult:
        """Validate changes made by Forge against expected changes."""
        if self.forge is None:
            return ToolResult(
                status="error",
                error="Forge not initialized"
            )
            
        try:
            # Get the current contents of the files
            file_contents = self.forge.get_file_contents(files)
            
            # Format a message for validation
            message = f"""Please validate if the following file changes match the expected changes.

Expected Changes:
{expected_changes}

Current File Contents:
{json.dumps(file_contents, indent=2)}

Please respond with a clear YES or NO and explain any discrepancies."""
            
            # Get clean response without making changes
            cleaned_response, _ = self.forge.get_clean_response(
                self.forge.chat(message)
            )
            
            # Parse the response
            if "YES" in cleaned_response.upper():
                return ToolResult(
                    status="success",
                    output=cleaned_response
                )
            else:
                return ToolResult(
                    status="error",
                    error=f"Validation failed: {cleaned_response}"
                )
                
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error validating changes: {str(e)}"
            )
