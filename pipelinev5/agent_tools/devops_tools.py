import json
import time
import select
import sys
import termios
import signal
from pathlib import Path
import subprocess
import tty
import os
import shutil
import fcntl
from prompts.tools_prompts import LLM_VALIDATION_TEMPLATE
from typing import Dict, List, Optional, Any
from prompts.devops_agent_prompts import DECISION_SUMMARY_PROMPT, STEP_SUMMARY_PROMPT
from pydantic import BaseModel
from ai_models.openai_models import get_open_ai
from utils.general_helper_functions import configure_logger
from langchain_core.prompts import PromptTemplate
from termcolor import colored
import google.generativeai as genai

logger = configure_logger(__name__)

class DecisionSummaryModel(BaseModel):
    tagline: str
    summary: str




#######################################################################
# Supabase Client, can remove and import when move to django
#######################################################################

import os
from supabase import create_client, Client
import traceback

class Supabase:
    def __init__(self, access_token: str = None, refresh_token: str = None, user_auth=False):
        url: str = os.getenv("SUPABASE_URL", "")
        key: str = os.getenv("SUPABASE_KEY", "")
        
        if not url or not key:
            raise ValueError("Supabase URL or Key is not set in the environment variables.")

        try:    
            self.supabase: Client = create_client(url, key)
            if user_auth:
                # Optionally set session details if required
                self.supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
                pass
        except Exception as e:
            traceback.print_exc()
            raise ValueError(f"Failed to initialize Supabase client: {str(e)}")
        
    def get_project_data(self, project_id: str):
        response = self.supabase.table("projects").select("*").eq("id", project_id).execute()
        data = response.data
        if not data:
            raise ValueError(f"No project data found for project {project_id}")
        if type(data) is list:
            return data[0]
        elif type(data) is dict:
            return data
        else:
            raise ValueError(f"Unexpected data type: {type(data)}")

    def set_aws_credentials(access_token: str = "", refresh_token: str = "", project_id: str = ""):
        # Retrieve variables from .env
        url: str = os.getenv("SUPABASE_URL") 
        key: str = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("Supabase URL or Key is not set in the environment variables.")

        try:
            supabase: Client = create_client(url, key)
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            
            # Execute the query
            response = supabase.table("projects").select("aws_access_key_id, aws_secret_access_key").eq("id", project_id).execute()
            
            if not response.data:
                raise ValueError(f"No AWS credentials found for project {project_id}")
                
            return response
            
        except Exception as e:
            raise ValueError(f"Failed to retrieve AWS credentials: {str(e)}")

    def update_project_data(self, project_id: str, codebase_understanding: dict) -> None:
        """Update project's codebase understanding in Supabase."""
        try:
            self.supabase.table("projects").update({
                "codebase_understanding": codebase_understanding
            }).eq("id", project_id).execute()
        except Exception as e:
            raise ValueError(f"Failed to update project data: {str(e)}")

    def get_integration_raw_data(self, integration_name: str, project_id: str):
        """
        Get raw data for a specific integration from the projects table.
        
        Args:
            integration_name: Name of the integration tool
            project_id: ID of the project
            
        Returns:
            Response object containing the data
            
        Raises:
            ValueError: If the query fails or returns invalid data
        """
        try:
            integration_column = f"{integration_name}_raw"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            response = response.data[0][integration_column]
            if not response:
                print(f"Failed to retrieve {integration_name} data")
                return None
                
            return str(response)
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")
    
    def get_integration_summarized_data(self, integration_name: str, project_id: str):
        """
        Get summarized data for a specific integration from the projects table.
        
        Args:
            integration_name: Name of the integration tool
            project_id: ID of the project
            
        Returns:
            Response object containing the data
            
        Raises:
            ValueError: If the query fails or returns invalid data
        """
        try:
            integration_column = f"{integration_name}_summary"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            response = response.data[0][integration_column]
            if not response:
                print(f"No {integration_name} summary")
                return None
            
            return str(response)
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")

#######################################################
# End of Supabase Client
#######################################################


artifactory_tools = ["artifactory", "nexus"]
cicd_tools = ["jenkins", "github", "gitlab", "circleci"]
cloud_tools = ["aws", "azure", "gcp"]
cm_tools = ["ansible", "chef", "puppet"]
container_tools = ["docker", "podman"]
networking_tools = ["istio", "consul"]
observability_tools = ["datadog", "new_relic", "splunk", "elasticsearch", "grafana", "prometheus"]
orchestration_tools = ["kubernetes", "docker_swarm"]

all_tools = (
    artifactory_tools 
    + cicd_tools
    + cloud_tools
    + cm_tools
    + container_tools
    + networking_tools
    + observability_tools
    + orchestration_tools
)

def summarize_with_llm(
    model_name: str,
    raw_data: str,
    prompt_instructions: str,
    api_key: str
) -> str:
    """
    Send raw data and instructions to the specified Gemini model, returning a summary.
    """
    if not genai:
        raise ImportError("Gemini library not installed or not imported properly.")
    # Create a Gemini model instance
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    # Build the prompt
    prompt = (
        f"{prompt_instructions}\n\n"
        "--- RAW DATA START ---\n"
        f"{raw_data}\n"
        "--- RAW DATA END ---\n"
    )
    
    # Generate the summary
    response = model.generate_content(prompt)
    return response.text

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
        
        # Handle output with no truncation
        if entry['result'].get('output'):
            text += f"Output: {entry['result']['output']}\n"
            
        # Handle error with no truncation
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
    
    def __init__(self, working_directory: str, subprocess_handler: Any, project_id: str = None):
        self.working_directory = Path(working_directory)
        self.subprocess_handler = subprocess_handler
        self.forge = None
        self.project_id = project_id
        
        # Make sure the working directory exists
        self.working_directory.mkdir(parents=True, exist_ok=True)
    
    def set_forge(self, forge: Any):
        """Set the Forge instance for code execution."""
        self.forge = forge
    
    ########################################################################
    #  Simple command and code execution
    ########################################################################
        
    def integration_info(self, query: str, integration_name: str):
        """
        Retrieve and summarize informaton about user's integrations.
        Args:
            query: The question or instruction for summarizing the data
            integration_name: Name of the integration tool
        
        Returns:
            str: Summarized integration data
        """

        if integration_name not in all_tools:
            return "Integration not found, specify the correct integration name."
        
        try:
            # Initialize Supabase client
            supabase_client = Supabase()
            
            # Get integration data
            response = supabase_client.get_integration_raw_data(integration_name, self.project_id)
            
            if not response or not response.data or not response.data[0]:
                return "No data found for the specified integration."
                
            raw_data = response.data[0]
            if not raw_data:
                return f"Empty data for {integration_name} integration."
                
            # Generate summary using LLM
            try:
                return summarize_with_llm("models/gemini-1.5-pro", raw_data, query, api_key=os.getenv("GOOGLE_API_KEY"))
            except Exception as e:
                return f"Error generating summary: {str(e)}"
                
        except Exception as e:
            return f"Error retrieving integration data: {str(e)}"

    def execute_command(
        self,
        command: str, 
        timeout: int = 30,
        cwd: Optional[str] = None
    ) -> ToolResult:
        """
        Execute a shell command with support for interactive input, timeout,
        and working-directory support. This version preserves your original
        sudo detection/modification and error handling while using a pseudoterminal (pty)
        to correctly handle commands that disable echo (for hidden input like passwords).
        
        When echo is enabled, an inactivity timeout is enforced. When echo is disabled,
        the timeout is suspended so the process will wait indefinitely for input.
        """
        try:
            if not command:
                return ToolResult(status="error", error="No command provided")
            
            # --- Preserve Original Sudo Modification Logic ---
            def is_sudo_command(cmd: str) -> bool:
                """Check if the command starts with sudo but doesn't already have -S flag"""
                return cmd.strip().startswith("sudo") and "-S" not in cmd

            def modify_sudo_command(cmd: str) -> str:
                """Add -S flag to sudo commands if not already present"""
                if is_sudo_command(cmd):
                    # Split after 'sudo' to preserve all other flags/args
                    parts = cmd.split("sudo", 1)
                    return f"sudo -S{parts[1]}"
                return cmd

            # Modify command if it's a sudo command.
            command = modify_sudo_command(command)
            
            effective_cwd = cwd if cwd else str(self.working_directory)
            print(f"\nExecuting command: {command}")
            print(f"Working directory: {effective_cwd}")
            # --- End Original Sudo/Directory Logic ---

            # Save the original terminal settings for sys.stdin.
            orig_term_settings = termios.tcgetattr(sys.stdin.fileno())
            try:
                # Put sys.stdin into raw mode to capture keystrokes immediately.
                tty.setraw(sys.stdin.fileno())
                
                # Create a new pseudoterminal pair.
                master_fd, slave_fd = os.openpty()
                # Duplicate the slave fd so we can later query its terminal attributes.
                slave_fd_dup = os.dup(slave_fd)
                
                # Spawn the subprocess with the slave fd as its stdin, stdout, and stderr.
                # preexec_fn=os.setsid ensures the child gets its own process group.
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=effective_cwd,
                    preexec_fn=os.setsid
                )
                
                # We no longer need the original slave_fd in the parent.
                os.close(slave_fd)
                
                # Set the master fd to non-blocking mode.
                flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
                fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                
                output_buffer = []
                last_activity = time.time()
                
                # Main loop: relay output from the child (via master_fd) to sys.stdout,
                # and relay user keystrokes from sys.stdin to the child.
                while True:
                    # Break out if the process has ended.
                    if process.poll() is not None:
                        break

                    now = time.time()
                    # --- New: Query the child’s terminal echo setting ---
                    try:
                        slave_attrs = termios.tcgetattr(slave_fd_dup)
                        # termios attributes: index 3 is lflag; if ECHO is set, echo is enabled.
                        echo_enabled = bool(slave_attrs[3] & termios.ECHO)
                    except Exception:
                        echo_enabled = True  # Default to enforcing timeout.

                    # Enforce timeout only if echo is enabled.
                    if echo_enabled and timeout and (now - last_activity) > timeout:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        return ToolResult(status="error", error=f"Command timed out after {timeout} seconds of inactivity")

                    # Use select to wait for data from either the child process or the user.
                    ready_fds, _, _ = select.select([master_fd, sys.stdin], [], [], 0.1)
                    for fd in ready_fds:
                        if fd == master_fd:
                            # Read output from the child process.
                            try:
                                data = os.read(master_fd, 1024)
                            except OSError:
                                data = b""
                            if data:
                                decoded = data.decode(errors="ignore")
                                sys.stdout.write(decoded)
                                sys.stdout.flush()
                                output_buffer.append(decoded)
                                last_activity = now
                        elif fd == sys.stdin:
                            try:
                                # Read user input from sys.stdin. In raw mode, this is character-by-character.
                                user_input = os.read(sys.stdin.fileno(), 1024)
                                if user_input:
                                    # Relay the user input to the child.
                                    os.write(master_fd, user_input)
                                    last_activity = now
                                    # If echo is disabled (e.g. password prompt), do not display the actual input.
                                    if not echo_enabled:
                                        sys.stdout.write("*****")
                                        sys.stdout.flush()
                                        output_buffer.append("*****")
                                    # Otherwise, if echo is enabled, let the child echo the characters.
                            except OSError:
                                pass

                # After the main loop, attempt to flush any remaining output.
                while True:
                    try:
                        rlist, _, _ = select.select([master_fd], [], [], 0.1)
                        if master_fd in rlist:
                            data = os.read(master_fd, 1024)
                            if not data:
                                break
                            decoded = data.decode(errors="ignore")
                            sys.stdout.write(decoded)
                            sys.stdout.flush()
                            output_buffer.append(decoded)
                        else:
                            break
                    except Exception:
                        break

                retcode = process.poll()
                output = "".join(output_buffer)
                if retcode == 0:
                    return ToolResult(status="success", output=output)
                else:
                    # Note: since stderr and stdout are merged in the pty, we just report the exit code.
                    return ToolResult(
                        status="error",
                        error=f"Command failed with exit code {retcode}",
                        output=output if output else None
                    )
            finally:
                # Restore the original terminal settings.
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, orig_term_settings)
                # Close the file descriptors.
                try:
                    os.close(master_fd)
                except Exception:
                    pass
                try:
                    os.close(slave_fd_dup)
                except Exception:
                    pass
        except Exception as e:
            return ToolResult(status="error", error=f"Error executing command: {str(e)}")
        
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

                    Remember that all the modifications you make should never be example modifications.
                    They should always be real modifications that are relevant to the instructions.
                    The code you add or change should be immediately usable, runnalbe and deployable with no further changes.

                    For example, you should never put in example code or example ids, because those make it so that the code isn't isntantly usable and reuqires further changes.
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
            if not file_path:
                return ToolResult(
                    status="error",
                    error="No file path provided"
                )
            
            effective_cwd = Path(cwd if cwd else str(self.working_directory)).resolve()
            full_path = Path(os.path.join(effective_cwd, file_path)).resolve()
            
            # Ensure parent directories exist
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if mode is not None:
                full_path.chmod(mode)
            
            return ToolResult(
                status="success",
                output=f"Successfully created file {file_path} with content:\n{content}"
            )
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error creating file: {str(e)}"
            )
        
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
    
    # def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> "ToolResult":
    #     """
    #     Use an LLM to compare the actual code changes to the expected changes.
    #     Return 'success' if it matches, else 'error'.
    #     """
    #     prompt_text = f"""We have code changes and an expected set of changes.
    #                     Instructions that were followed: {instructions}

    #                     Expected changes:
    #                     {expected_changes}

    #                     Actual code changes:
    #                     {code}

    #                     Check whether the content matches the expected content.
    #                     """
    #     return self._llm_validation_check(prompt_text)
    
    def validate_code_changes(self, code: str, instructions: str, expected_changes: str) -> "ToolResult":
        """
        Use an LLM to compare the actual code changes to the expected changes.
        Return 'success' if it matches, else 'error'.
        """
        try:
            # Check if code is a tuple containing EditResult
            if isinstance(code, tuple):
                edit_result, file_contents = code
                # Extract the modified files content
                code = "\n".join(file_contents.values())
            elif isinstance(code, dict):
                # If code is a dictionary of file contents
                code = "\n".join(code.values())

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

    def rollback_commits(self, num_commits: int = 1) -> ToolResult:
        """Roll back the specified number of commits."""
        try:
            if not hasattr(self, 'forge') or not self.forge:
                return ToolResult(
                    status="error",
                    error="Forge not initialized"
                )
                
            result = self.forge.rollback_commits(num_commits)
            
            if result.success:
                return ToolResult(
                    status="success",
                    output=f"Successfully rolled back {num_commits} commit(s)"
                )
            else:
                return ToolResult(
                    status="error",
                    error=result.error or "Failed to roll back commits"
                )
                
        except Exception as e:
            return ToolResult(
                status="error", 
                error=f"Error during rollback: {str(e)}"
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
        

        
