import os
import logging
from pathlib import Path
import re
from typing import Optional, Dict, List, Generator, Tuple, Union, Any
from dataclasses import dataclass

from forge.coders import Coder
from forge.main import main as cli_main
from forge.models import Model
import difflib
import patch

@dataclass
class EditResult:
    """Represents the result of an edit operation"""
    files_changed: List[str]
    commit_hash: Optional[str] = None 
    success: bool = True
    error: Optional[str] = None
    message: Optional[str] = None
    diff: Optional[Dict[str, str]] = None

class ForgeWrapper:
    """A wrapper class to interact with Forge programmatically"""
    
    def __init__(self, 
                 files: Optional[List[str]] = None,
                 model: str = "gpt-4o",
                 git_root: Optional[str] = None,
                 stream: bool = False,
                 verbose: bool = False,
                 log_level: str = "INFO",
                 auto_commit: bool = True,
                 api_key: Optional[str] = None,
                 api_base: Optional[str] = None,
                 env_vars: Optional[Dict[str, str]] = None):
        """Initialize the Forge wrapper"""
        # Setup logging
        self.logger = logging.getLogger("ForgeWrapper")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.files = files or []
        self.model = model
        self.git_root = git_root
        self.stream = stream
        self.verbose = verbose
        self.auto_commit = auto_commit
        
        # Setup environment
        self._setup_environment(api_key, api_base, env_vars)
        
        # Validate files exist
        for file in self.files:
            if not Path(file).exists():
                raise FileNotFoundError(f"File not found: {file}")

        # Initialize the coder
        try:
            self._initialize_coder()
        except Exception as e:
            self.logger.error(f"Failed to initialize Forge coder: {str(e)}")
            raise

    def _initialize_coder(self) -> None:
        """Initialize the Forge coder with appropriate arguments"""
        print(f"ForgeWrapper initializing coder with git_root: {self.git_root}")  # Debug print
        args = [
            "--model", self.model,
            "--yes-always",  # Don't prompt for confirmations
        ]
        
        if self.files:
            args.extend(["--file"] + self.files)
            
        if not self.stream:
            args.append("--no-stream")
            
        if self.verbose:
            args.append("--verbose")
            
        if not self.auto_commit:
            args.append("--no-auto-commits")

        self.coder = cli_main(args, return_coder=True, force_git_root=self.git_root)
        if not isinstance(self.coder, Coder):
            raise ValueError(f"Failed to initialize Forge coder: {self.coder}")

    def get_current_files_content(self) -> Dict[str, str]:
        contents = {}
        for file in self.coder.get_all_abs_files():
            normalized_path = self._normalize_path(file)
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    contents[normalized_path] = f.read()
            except FileNotFoundError:
                contents[normalized_path] = ''
        return contents

    def get_edited_files_content(self, edit_result: EditResult) -> Dict[str, str]:  # Fixed return type
        new_contents = {}
        for file in edit_result.files_changed:
            normalized_path = self._normalize_path(file)
            try:
                with open(normalized_path, 'r') as f:
                    new_contents[normalized_path] = f.read()
            except FileNotFoundError:
                print(f"File not found in get_edited_files_content: {normalized_path}")
                new_contents[normalized_path] = ''
                
            # try:
            #     if normalized_path in old_contents:
            #         with open(file, 'w') as f:
            #             f.write(old_contents[normalized_path])
            #     else:
            #         os.remove(file)
            # except FileNotFoundError:
            #     pass
        return new_contents
    
    def generate_diffs(self, old_contents: Dict[str, str], new_contents: Dict[str, str]) -> Dict[str, str]:
        """
        Generate unified diffs between old and new file contents.
        
        Args:
            old_contents: Dict mapping filenames to their original content
            new_contents: Dict mapping filenames to their new content
            
        Returns:
            Dict mapping filenames to their unified diff strings
        """
        diffs = {}
        
        def print_contents(contents: Dict[str, str]) -> None:
            for filename, content in contents.items():
                print(f"File: {filename} - {len(content)} lines")
            print("\n" + "="*50 + "\n")
        
        # print("Old contents:")
        # print_contents(old_contents)
        # print("New contents:")
        # print_contents(new_contents)
        
        for filename in set(new_contents.keys()):
            try:
                old = old_contents.get(filename, '').splitlines(keepends=True)
                new = new_contents.get(filename, '').splitlines(keepends=True)
                
                # Special handling for new/deleted files
                if filename not in old_contents:
                    fromfile = '/dev/null'  # Standard way to indicate new file
                else:
                    fromfile = f'a/{filename}'
                    
                tofile = f'b/{filename}'
                
                diff = ''.join(difflib.unified_diff(
                    old,
                    new,
                    fromfile=fromfile,
                    tofile=tofile,
                    lineterm=''
                ))
                
                if diff:  # Only include files that actually changed
                    diffs[filename] = diff
                    
            except Exception as e:
                self.logger.error(f"Error generating diff for {filename}: {str(e)}")
                diffs[filename] = f"Error generating diff: {str(e)}"
                
        return diffs
        

    def chat(self, message: str, mode: str = "ask", auto_apply=True) -> Union[str, EditResult]:
        """Send a message to the LLM and get the response"""
        if mode != "code":
            auto_apply = False
        
        try:
            if self.stream:
                out = ""
                for chunk in self.chat_stream(message):
                    out += chunk if type(chunk) == str else ""
                return out
            
            self.logger.debug(f"Sending message: {message}")
            old_contents = None
            if not auto_apply:
                old_contents = self.get_current_files_content()
            self.coder.io.add_to_input_history(f"/{mode} " + message + ("\n\nDON'T ACTUALLY EDIT THE CODE YOURSELF, THIS IS /ASK MODE." if mode == "ask" else ""))
            response = self.coder.run(with_message=message)
            
            # Check if files were edited
            if self.coder.forge_edited_files:
                er = self._create_edit_result()
                if not auto_apply:
                    new_contents = self.get_edited_files_content(er)
                    er.diff = self.generate_diffs(old_contents, new_contents)
                    if self.auto_commit:
                        self.undo_last_edit()
                return er
                
            return response

        except Exception as e:
            self.logger.error(f"Error during chat: {str(e)}")
            raise

    def _prepare_edit_context(self, auto_apply: bool) -> Optional[Dict[str, str]]:
        """Prepare the editing context by getting current file contents if needed"""
        if not auto_apply:
            return self.get_current_files_content()
        return None

    def _handle_edit_completion(self, old_contents: Optional[Dict[str, str]], auto_apply: bool) -> Optional[EditResult]:
        """Handle completion of an edit operation"""
        if not self.coder.forge_edited_files:
            # print("No edits made")
            return None
            
        er = self._create_edit_result()
        if not auto_apply:
            new_contents = self.get_edited_files_content(er)
            er.diff = self.generate_diffs(old_contents, new_contents)
            if self.auto_commit:
                self.undo_last_edit()
        return er

    def chat_stream(self, message: str, mode: str = "ask", auto_apply=True) -> Generator[str, None, None]:
        """Stream a chat response from the LLM"""
        if not self.stream:
            raise ValueError("Streaming is disabled. Initialize with stream=True to use chat_stream")
            
        try:
            self.logger.debug(f"Streaming message: {message}")
            
            # Get initial file contents if needed
            old_contents = self._prepare_edit_context(auto_apply)
            
            self.coder.io.add_to_input_history(f"/{mode} " + message + 
                ("\n\nDON'T ACTUALLY EDIT THE CODE YOURSELF, THIS IS /ASK MODE." if mode == "ask" else ""))
            
            # Stream the response
            for chunk in self.coder.run_stream(message):
                yield chunk
            
            # Handle edits after streaming completes
            edit_result = self._handle_edit_completion(old_contents, auto_apply)
            if edit_result:
                yield edit_result
                
        except Exception as e:
            self.logger.error(f"Error during chat stream: {str(e)}")
            raise

    def _create_edit_result(self) -> EditResult:
        """Create an EditResult object from the current coder state"""
        result = EditResult(
            files_changed=self.coder.forge_edited_files,
            commit_hash=self.coder.last_forge_commit_hash,
            success=True
        )
        
        if result.commit_hash:
            try:
                result.diff = self.coder.repo.diff_commits(
                    self.coder.pretty,
                    f"{result.commit_hash}~1",
                    result.commit_hash,
                )
            except Exception as e:
                self.logger.warning(f"Failed to get diff: {str(e)}")
                
        return result

    def add_file(self, filepath: Union[str, Path]) -> None:
        """Add a file to the chat context"""
        try:
            filepath = Path(filepath).resolve()
            if not filepath.exists():
                raise FileNotFoundError(f"File not found: {filepath}")
                
            filepath_str = str(filepath)
            self.logger.debug(f"Adding file to context: {filepath_str}")
            self.coder.add_rel_fname(filepath_str)
            self.files.append(filepath_str)
            
        except Exception as e:
            self.logger.error(f"Error adding file: {str(e)}")
            raise

    def remove_file(self, filepath: Union[str, Path]) -> None:
        """Remove a file from the chat context"""
        try:
            filepath = str(Path(filepath).resolve())
            if filepath not in self.files:
                raise ValueError(f"File not in context: {filepath}")
                
            self.logger.debug(f"Removing file from context: {filepath}")
            self.coder.drop_rel_fname(filepath)
            self.files.remove(filepath)
            
        except Exception as e:
            self.logger.error(f"Error removing file: {str(e)}")
            raise

    def get_files(self) -> List[str]:
        """Get list of files currently in chat context"""
        return [str(Path(fp).resolve()) for fp in self.coder.abs_fnames]

    def clear_history(self) -> None:
        """Clear the chat history"""
        self.logger.debug("Clearing chat history")
        self.coder.done_messages = []
        self.coder.cur_messages = []

    def undo_last_edit(self) -> Optional[EditResult]:
        """Undo the last edit made by Forge"""
        try:
            self.logger.debug("Attempting to undo last edit")
            if not self.coder.last_forge_commit_hash:
                self.logger.info("No edits to undo")
                return None
                
            old_hash = self.coder.last_forge_commit_hash
            self.coder.commands.cmd_undo(None)
            
            result = EditResult(
                files_changed=self.coder.forge_edited_files,
                commit_hash=old_hash,
                success=True
            )
            return result
            
        except Exception as e:
            self.logger.error(f"Error during undo: {str(e)}")
            result = EditResult(
                files_changed=[],
                success=False,
                error=str(e)
            )
            return result
        
    def _normalize_path(self, path: Union[str, Path]) -> str:
        """Normalize path to string format used in diffs"""
        # for both types, this checks if path has self.coder.root in it - if so, add path to self.coder.root otherwise just use path as is
        if type(path) == Path:
            path = str(path)
        if self.coder.root in path:
            return str(Path(path).resolve())
        else:
            return os.path.join(self.coder.root, path)

    def apply_diffs(self, diffs: Dict[str, str]) -> EditResult:
        """
        Apply the specified diffs to the files.
        
        Args:
            diffs: Dict mapping filenames to their diff content
            
        Returns:
            EditResult object containing the results of applying the diffs
        """
        files_changed = []
        try:
            for filename, diff_content in diffs.items():
                normalized_path = self._normalize_path(filename)
                
                # Parse the diff to get the changes
                current_content = ''
                try:
                    with open(normalized_path, 'r', encoding='utf-8') as f:
                        current_content = f.read()
                except FileNotFoundError:
                    # File doesn't exist yet, which is fine for new files
                    pass
                    
                # Apply the diff using patch
                patcher = patch.PatchSet(diff_content.splitlines(True))
                
                try:
                    # Create directories if they don't exist
                    os.makedirs(os.path.dirname(normalized_path), exist_ok=True)
                    
                    # Apply the patch
                    with open(normalized_path, 'w', encoding='utf-8') as f:
                        result = patcher.apply(current_content.splitlines(True))
                        if result:
                            f.writelines(result)
                            files_changed.append(normalized_path)
                        else:
                            raise ValueError(f"Failed to apply diff to {normalized_path}")
                            
                except Exception as e:
                    return EditResult(
                        files_changed=list(files_changed),
                        success=False,
                        error=f"Error applying diff to {normalized_path}: {str(e)}"
                    )
                    
            return EditResult(
                files_changed=list(files_changed),
                success=True,
                message="Successfully applied diffs"
            )
            
        except Exception as e:
            return EditResult(
                files_changed=list(files_changed),
                success=False,
                error=f"Error applying diffs: {str(e)}"
            )
         

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return self.coder.main_model.info

    def set_model(self, model_name: str) -> None:
        """Change the active model"""
        try:
            self.logger.debug(f"Switching to model: {model_name}")
            self.model = model_name
            self._initialize_coder()
        except Exception as e:
            self.logger.error(f"Error switching model: {str(e)}")
            raise

    @property
    def available_models(self) -> List[str]:
        """Get list of available models"""
        try:
            from forge.models import OPENAI_MODELS, ANTHROPIC_MODELS
            return OPENAI_MODELS + ANTHROPIC_MODELS
        except ImportError:
            self.logger.warning("Could not import model lists from forge.models")
            return []

    def get_chat_history(self) -> List[Dict[str, str]]:
        """Get the current chat history"""
        return self.coder.done_messages + self.coder.cur_messages

    def _setup_environment(self, api_key: Optional[str], api_base: Optional[str], 
                         env_vars: Optional[Dict[str, str]]) -> None:
        """Setup environment variables for API access"""
        # Set custom environment variables
        if env_vars:
            for key, value in env_vars.items():
                os.environ[key] = value
                self.logger.debug(f"Set environment variable: {key}")

        # Handle OpenAI credentials
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            self.logger.debug("Set OPENAI_API_KEY from parameter")
        elif "OPENAI_API_KEY" not in os.environ:
            raise ValueError(
                "OpenAI API key not found. Either pass api_key parameter or "
                "set OPENAI_API_KEY environment variable"
            )

        if api_base:
            os.environ["OPENAI_API_BASE"] = api_base
            self.logger.debug("Set OPENAI_API_BASE from parameter")

    @classmethod
    def from_env_file(cls, env_file: str, **kwargs) -> 'ForgeWrapper':
        """Create a ForgeWrapper instance using environment variables from a file"""
        from dotenv import load_dotenv
        
        if not load_dotenv(env_file, override=True):
            raise ValueError(f"Failed to load environment file: {env_file}")
        
        # Get the API key from the newly loaded env file
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            kwargs["api_key"] = api_key
            
        return cls(**kwargs) 

    def _clean_output(self, text: str) -> str:
        """Remove ANSI escape sequences and clean up forge output"""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)
        
        # Remove forge's formatting markers
        text = re.sub(r'────+', '', text)
        
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def get_clean_response(self, response: Union[str, EditResult]) -> Tuple[str, Dict[str, str]]:
        """
        Get cleaned response and edited file contents
        
        Returns:
            Tuple containing:
            - Cleaned response text
            - Dictionary of {filename: content} for edited files
        """
        edited_files = {}
        
        # Handle EditResult
        if isinstance(response, EditResult):
            response_text = str(response)
            if response.files_changed:
                for file in response.files_changed:
                    file = self.coder.abs_root_path(file)
                    try:
                        with open(file, 'r') as f:
                            edited_files[file] = f.read()
                    except Exception as e:
                        self.logger.error(f"Error reading edited file {file}: {str(e)}")
        else:
            response_text = str(response)

        # Clean the response text
        cleaned_text = self._clean_output(response_text)
        
        return cleaned_text, edited_files

    def chat_and_get_updates(self, message: str) -> Tuple[str, Dict[str, str]]:
        """
        Send a chat message and get cleaned response with any file updates
        
        Args:
            message: Message to send to the LLM
            
        Returns:
            Tuple containing:
            - Cleaned response text
            - Dictionary of {filename: content} for edited files
        """
        print(f"Files in chat context: {self.get_files()}")
        print(f"ABS fnames{self.coder.abs_fnames}")
        response = self.chat(message, mode="code")
        return self.get_clean_response(response)

    def get_file_contents(self, files: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Get contents of specified files or all files in chat context
        
        Args:
            files: Optional list of files to get contents for. If None, uses files in chat context.
            
        Returns:
            Dictionary of {filename: content}
        """
        files_to_read = files if files is not None else self.get_files()
        contents = {}
        
        for file in files_to_read:
            try:
                with open(file, 'r') as f:
                    contents[file] = f.read()
            except Exception as e:
                self.logger.error(f"Error reading file {file}: {str(e)}")
                
        return contents 