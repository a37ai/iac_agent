# pipelinev5/utils/subprocess_handler.py

import subprocess
from typing import Dict, Optional, Union
import os
from pathlib import Path

class SubprocessHandler:
    def __init__(self, working_directory: Union[str, Path]):
        """Initialize the subprocess handler with a working directory."""
        self.working_directory = Path(working_directory)

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        env: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Execute a shell command and return the result.
        
        Args:
            command: The command to execute
            timeout: Optional timeout in seconds
            env: Optional environment variables
            
        Returns:
            Dict containing status, stdout, and stderr
        """
        try:
            # Merge current environment with provided env vars
            current_env = os.environ.copy()
            if env:
                current_env.update(env)

            # Execute command
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.working_directory),
                env=current_env
            )

            # Check if command was successful
            if process.returncode == 0:
                return {
                    "status": "success",
                    "stdout": process.stdout,
                    "stderr": process.stderr
                }
            else:
                return {
                    "status": "error",
                    "stdout": process.stdout,
                    "stderr": process.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                "status": "error",
                "stdout": "",
                "stderr": str(e)
            }