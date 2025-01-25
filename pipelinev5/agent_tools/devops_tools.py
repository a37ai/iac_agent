import json
import time
import select
from pathlib import Path
import subprocess
import os
import shutil
import requests
from prompts.tools_prompts import LLM_VALIDATION_TEMPLATE
from typing import Dict, List, Optional, Any
from prompts.devops_agent_prompts import DECISION_SUMMARY_PROMPT, STEP_SUMMARY_PROMPT
from pydantic import BaseModel
from ai_models.openai_models import get_open_ai
from utils.general_helper_functions import configure_logger
from langchain_core.prompts import PromptTemplate
from termcolor import colored

logger = configure_logger(__name__)

class DecisionSummaryModel(BaseModel):
    tagline: str
    summary: str

def generate_quick_summary_from_decision(decision: "LLMDecision") -> (str, str):
    """
    Generate a short tagline and summary from the LLM decision.
    Returns a tuple of (tagline, summary).
    """
    try:
        llm = get_open_ai(temperature=0.3, model='gpt-4o')

        # Escape any curly braces in the content and description
        safe_content = str(decision.content).replace("{", "{{").replace("}", "}}")
        safe_description = str(decision.description).replace("{", "{{").replace("}", "}}")
        safe_reasoning = str(decision.reasoning).replace("{", "{{").replace("}", "}}")

        prompt_text = DECISION_SUMMARY_PROMPT.format(
            decision_type=decision.type,
            description=safe_description,
            content=safe_content,
            reasoning=safe_reasoning
        )

        response = llm.invoke(prompt_text)
        try:
            # Clean the response content of any markdown formatting
            content = response.content.strip()
            # Remove markdown code block if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            content = content.strip()
            
            data = json.loads(content)
            # Validate it has tagline and summary
            validated = DecisionSummaryModel(**data)
            return validated.tagline, validated.summary
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse decision summary as JSON: {response.content}\nError: {e}")
            # Provide meaningful defaults instead of "No tagline/summary"
            if decision.type == "end":
                return "Mission Accomplished", "The current step has been completed successfully. Moving to next step."
            return (
                f"DevOps {decision.type.replace('_', ' ').title()} in Progress",
                f"Performing a {decision.type.replace('_', ' ')} operation. {safe_description}"
            )
    except Exception as e:
        logger.warning(f"Could not generate quick summary: {str(e)}")
        return (
            f"DevOps {decision.type.replace('_', ' ').title()} in Progress",
            f"Performing a {decision.type.replace('_', ' ')} operation. {safe_description}"
        )

##############################################################################
#                        Helper Formatting Functions
##############################################################################

def format_knowledge_sequence(knowledge_sequence: List[Dict], step_description: str) -> str:
    """Convert the knowledge_sequence (tool calls + outcomes) into text."""
    if not knowledge_sequence:
        return "No tool calls or outcomes for this step yet. This is the first time we're seeing this step."
    
    text = f"Current Step: {step_description}\n\n"
    for i, entry in enumerate(knowledge_sequence, 1):
        text += f"Action {i}:\n"
        text += f"Type: {entry['action_type']}\n"
        text += f"Input: {entry['action']}\n"
        text += f"Result: {entry['result']['status']}\n"
        if entry['result'].get('output'):
            shortened = entry['result']['output'][:200]
            text += f"Output: {shortened}...\n"
        if entry['result'].get('error'):
            text += f"Error: {entry['result']['error']}\n"
        text += "\n"
    return text

def format_completed_steps(completed_steps: List[Dict]) -> str:
    """Convert completed steps into text for LLM context."""
    if not completed_steps:
        return "No steps completed yet."
    
    text = "Completed Steps:\n"
    for i, s in enumerate(completed_steps, 1):
        text += f"Step {i}: {s['description']}\n"
        text += f"Status: {s['status']}\n"
        if 'summary' in s:
            text += f"Summary: {s['summary'].get('summary', 'No summary available')}\n"
        text += "\n"
    return text

##############################################################################
#                        Summarization for Step
##############################################################################

def format_step_knowledge(knowledge_sequence: List[Dict], step_description: str) -> str:
    """Convert the knowledge_sequence (tool calls + outcomes) into text."""
    if not knowledge_sequence:
        return "No execution history for this step."
    
    text = f"Current Step: {step_description}\n\n"
    for i, entry in enumerate(knowledge_sequence, 1):
        text += f"Action {i}:\n"
        text += f"Type: {entry['action_type']}\n"
        text += f"Input: {entry['action']}\n"
        text += f"Result: {entry['result']['status']}\n"
        if entry['result'].get('output'):
            shortened = entry['result']['output'][:200]
            text += f"Output: {shortened}...\n"
        if entry['result'].get('error'):
            text += f"Error: {entry['result']['error']}\n"
        text += "\n"
    return text

def summarize_step_knowledge(knowledge_sequence: List[Dict], step_description: str) -> Dict:
    """Use an LLM to summarize everything that happened in this step."""
    if not knowledge_sequence:
        return {
            "summary": "No actions taken",
            "key_learnings": [],
            "relevant_for_future": []
        }
    

    text_data = format_step_knowledge(knowledge_sequence, step_description)
    
    prompt = PromptTemplate(
        template=STEP_SUMMARY_PROMPT,
        input_variables=["step_data"]
    )
    
    try:
        llm = get_open_ai(temperature=0.1, model='gpt-4o')
        response = llm.invoke(prompt.format(step_data=text_data))
        
        # Try to parse JSON response
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                logger.warning(f"Failed to parse summary response: {response.content}")
                return {
                    "summary": "Step completed but summary generation failed",
                    "key_learnings": [],
                    "relevant_for_future": []
                }
    except Exception as e:
        logger.warning(f"Error summarizing step: {e}")
        return {
            "summary": "Step completed but summary generation failed",
            "key_learnings": [],
            "relevant_for_future": []
        }

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
        timeout: Optional[int] = 20,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """
        Execute a shell command in a subprocess with proper interactive input support.
        Uses non-blocking I/O to handle input requests naturally.
        """
        try:
            effective_cwd = cwd if cwd else str(self.working_directory)
            print(colored(f"\nExecuting command: {command}", 'yellow'))
            
            # Create process with pipes
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=str(effective_cwd)
            )
            
            output_buffer = []
            current_line = []
            start_time = time.time()
            
            def read_stream(stream):
                """Helper to read from a stream."""
                try:
                    return stream.read1().decode('utf-8')
                except (IOError, BlockingIOError):
                    return None
            
            # Set non-blocking mode
            import fcntl
            import os
            for stream in [process.stdout, process.stderr]:
                flags = fcntl.fcntl(stream, fcntl.F_GETFL)
                fcntl.fcntl(stream, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            while True:
                # Check timeout
                if timeout and time.time() - start_time > timeout:
                    process.kill()
                    return ToolResult(
                        status="error",
                        error=f"Command timed out after {timeout} seconds"
                    )

                # Check for output
                readable, writable, _ = select.select(
                    [process.stdout, process.stderr],
                    [process.stdin],
                    [],
                    0.1
                )

                # Handle output
                for stream in readable:
                    data = read_stream(stream)
                    if data:
                        if stream == process.stderr:
                            print(colored(data, 'red'), end='', flush=True)
                        else:
                            print(data, end='', flush=True)
                        output_buffer.append(data)

                # Check if process has finished
                retcode = process.poll()
                if retcode is not None:
                    # Get any remaining output
                    try:
                        stdout, stderr = process.communicate(timeout=0.1)
                        if stdout:
                            stdout = stdout.decode('utf-8')
                            print(stdout, end='', flush=True)
                            output_buffer.append(stdout)
                        if stderr:
                            stderr = stderr.decode('utf-8')
                            print(colored(stderr, 'red'), end='', flush=True)
                            output_buffer.append(stderr)
                    except subprocess.TimeoutExpired:
                        pass
                    break

                # Check if input is needed
                if not readable:
                    try:
                        user_input = input()
                        if user_input.strip().lower() == 'exit':
                            process.kill()
                            return ToolResult(
                                status="success",
                                output=''.join(output_buffer)
                            )
                        process.stdin.write(user_input.encode('utf-8') + b'\n')
                        process.stdin.flush()
                        output_buffer.append(f"{user_input}\n")
                        start_time = time.time()  # Reset timeout after input
                    except (EOFError, KeyboardInterrupt):
                        process.kill()
                        return ToolResult(
                            status="error",
                            error="Input interrupted"
                        )

                time.sleep(0.01)  # Prevent CPU thrashing

            output = ''.join(output_buffer)
            if retcode == 0:
                return ToolResult(
                    status="success",
                    output=output
                )
            else:
                return ToolResult(
                    status="error",
                    error=f"Command failed with exit code {retcode}",
                    output=output
                )

        except Exception as e:
            import traceback
            return ToolResult(
                status="error",
                error=f"Error executing command: {str(e)}\n{traceback.format_exc()}"
            )
    
    def modify_code(self, code: str, instructions: str, cwd: Optional[str] = None) -> "ToolResult":
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
    
    def delete_file(self, file_path: str, cwd: Optional[str] = None) -> "ToolResult":
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
    ) -> "ToolResult":
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
    ) -> "ToolResult":
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
    
    def run_file(self, file_path: str, args: Optional[List[str]] = None, cwd: Optional[str] = None) -> "ToolResult":
        """Execute a file directly (like a script)."""
        try:
            effective_cwd = Path(cwd if cwd else str(self.working_directory)).resolve()
            full_path = Path(os.path.join(effective_cwd, file_path)).resolve()
            
            if not full_path.exists():
                return ToolResult(status="error", error=f"File not found: {file_path}")
            
            # Use python interpreter for .py files
            if file_path.endswith('.py'):
                cmd = ['python', str(full_path)]
            else:
                cmd = [str(full_path)]
                
            if args:
                cmd.extend(args)
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(effective_cwd))
            return ToolResult(status="success", output=result.stdout)
            
        except subprocess.CalledProcessError as e:
            return ToolResult(status="error", error=f"Process error: {e.stderr}")
        except Exception as e:
            return ToolResult(status="error", error=str(e))
        
    ########################################################################
    #  Human involvement
    ########################################################################
    
    def ask_human_for_information(self, question: str) -> "ToolResult":
        """Prompt the user for information via CLI and return their response."""
        try:
            print(f"\n[DEVOPS AGENT QUESTION]: {question}")
            answer = input("Your response: ").strip()
            return ToolResult(status="success", output=answer)
        except Exception as e:
            return ToolResult(status="error", error=str(e))

    def ask_human_for_intervention(self, explanation: str) -> "ToolResult":
        """Wait for user intervention and explanation before proceeding."""
        try:
            print(f"\n[DEVOPS AGENT INTERVENTION REQUIRED]: {explanation}")
            print("Please perform the necessary actions and type 'done' when finished.")
            while True:
                user_input = input("Type 'done' when finished: ").strip().lower()
                if user_input == "done":
                    break
            user_explanation = input("Please explain what you did: ").strip()
            return ToolResult(status="success", output=user_explanation)
        except Exception as e:
            return ToolResult(status="error", error=str(e))
    
    ########################################################################
    #  LLM-based validations (via langchain_openai + custom prompts)
    ########################################################################
    
    def _llm_validation_check(self, prompt_text: str) -> "ToolResult":
        """
        Helper: Use an LLM to compare or validate correctness.
        Expect a JSON with "valid": "YES"/"NO" and an "explanation".
        """
        try:
            llm = get_open_ai(temperature=0.0, model='gpt-4o')

            prompt = PromptTemplate(
                template=LLM_VALIDATION_TEMPLATE,
                input_variables=["context"]
            )
            
            formatted_prompt = prompt.format(context=prompt_text)
            response = llm.invoke(formatted_prompt)
            
            # Try to parse as JSON, but handle string responses as well
            try:
                if isinstance(response.content, str):
                    if response.content.strip().startswith('{'):
                        data = json.loads(response.content.strip())
                    else:
                        # If not JSON, create a simple structure
                        data = {
                            "valid": "YES" if "valid" in response.content.lower() else "NO",
                            "explanation": response.content.strip()
                        }
                else:
                    data = response.content

                valid = str(data.get("valid", "")).upper()
                explanation = data.get("explanation", "No explanation provided.")
                
                if valid == "YES":
                    return ToolResult(status="success", output=explanation)
                else:
                    return ToolResult(status="error", error=explanation)
            
            except json.JSONDecodeError as je:
                # Handle non-JSON responses gracefully
                if "valid" in response.content.lower():
                    return ToolResult(status="success", output=response.content)
                else:
                    return ToolResult(status="error", error=response.content)
                
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"LLM validation failed: {str(e)}"
            )

    def validate_command_output(self, command_output: str, expected_behavior: str) -> "ToolResult":
        """
        Use an LLM to compare the actual command output to the expected behavior.
        Return 'success' if it matches, else 'error'.
        """
        prompt_text = f"""Compare the actual command output to an expected behavior.

                        Expected:
                        {expected_behavior}

                        Actual:
                        {command_output}

                        Check whether the content matches the expected content.
                        """
        return self._llm_validation_check(prompt_text)
    
    def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> "ToolResult":
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

                        Check whether the content matches the expected content.
                        """
        return self._llm_validation_check(prompt_text)
    
    def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> "ToolResult":
            """
            Use an LLM to compare the actual code changes to the expected changes.
            Return 'success' if it matches, else 'error'.
            """
            try:
                # First check if the input is JSON formatted
                if isinstance(code, str) and code.startswith('{'):
                    try:
                        parsed = json.loads(code)
                        if isinstance(parsed, dict):
                            # Extract actual code from JSON if it's in the expected format
                            code = parsed.get('code', code)
                            instructions = parsed.get('instructions', instructions)
                            expected_changes = parsed.get('expected_changes', expected_changes)
                    except json.JSONDecodeError:
                        pass  # If JSON parsing fails, use the original strings

                prompt_text = f"""We have code changes and an expected set of changes.
                                Instructions that were followed: {instructions}

                                Expected changes:
                                {expected_changes}

                                Actual code changes:
                                {code}

                                Analyze whether the code matches the expected changes, focusing on:
                                1. Variable names and references
                                2. Resource configurations
                                3. Overall structure and syntax

                                Validation criteria:
                                - All variable references should be consistent
                                - Code should follow proper syntax for its language
                                - Changes should match the expected modifications
                                """
                
                result = self._llm_validation_check(prompt_text)
                
                if result.status == "error":
                    # Add more context to the error message
                    result.error = f"Code validation failed: {result.error}"
                else:
                    result.output = f"Code validation passed: {result.output}"
                
                return result

            except Exception as e:
                return ToolResult(
                    status="error",
                    error=f"Error during code validation: {str(e)}"
                )
            
    def validate_file_output(self, file_content: str, expected_content: str) -> "ToolResult":
        """
        Use an LLM to compare the actual file content to the expected content.
        Return 'success' if it matches, else 'error'.
        """
        prompt_text = f"""Compare the actual file content to the expected content.

                        Expected:
                        {expected_content}

                        Actual:
                        {file_content}

                        Check whether the content matches the expected content.
                        """
        
        return self._llm_validation_check(prompt_text)

    
    def retrieve_documentation(self, query: str) -> "ToolResult":
        """
        Retrieve documentation or relevant information using the Perplexity API.

        :param query: The query string for which to retrieve documentation.
        :return: ToolResult with API response or error.
        """
        api_token = os.getenv("PERPLEXITY_API_TOKEN")

        if not api_token:
            return ToolResult(
                status="error",
                error="API token not found in environment variables."
            )

        api_url = "https://api.perplexity.ai/chat/completions" 

        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system", 
                    "content": "Be precise and concise."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": "Optional",
            "temperature": 0.2,
            "top_p": 0.9,
            "search_domain_filter": ["perplexity.ai"],
            "return_images": False,
            "return_related_questions": False,
            "search_recency_filter": "month",
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1
        }
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            return ToolResult(
                status="success",
                output=json.dumps(response.json())
            )
        except requests.exceptions.RequestException as e:
            return ToolResult(
                status="error",
                error=str(e)
            )
                
    def end_step(self) -> "ToolResult":
        """Handle the completion of a step."""
        try:
            return ToolResult(
                status="success",
                output="Step completed successfully"
            )
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error ending step: {str(e)}"
            )
        

        
