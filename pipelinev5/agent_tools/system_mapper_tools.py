from typing import Dict, List, Optional
import os
import git
import json
from pathlib import Path
from dotenv import load_dotenv
import logging
import shutil
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
import time
from utils.general_helper_functions import configure_logger, load_config
from prompts.system_mapper_prompts import ANALYZE_FILE_TEMPLATE, GENERATE_OVERVIEW_TEMPLATE
from ai_models.openai_models import get_open_ai

logger = configure_logger(__name__)

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

class FileAnalysis(BaseModel):
    """Schema for file analysis output"""
    main_purpose: str = Field(description="The main purpose and functionality of the file")
    key_components: List[str] = Field(description="Key components, classes, or functions")
    patterns: List[str] = Field(description="Important patterns and architectural decisions")
    devops_relevance: Dict[str, str] = Field(
        description="DevOps-specific aspects of the file",
        default_factory=lambda: {
            "configuration": "None",
            "infrastructure": "None",
            "pipeline": "None",
            "security": "None",
            "monitoring": "None"
        }
    )
    dependencies: List[str] = Field(
        description="External dependencies and integrations",
        default_factory=list
    )

class SystemMapper:
    def __init__(self, memory_context=None):
        load_dotenv()
        # Get the pipelinev2 directory path
        self.base_dir = Path.cwd()
        self.local_path = Path(os.getenv('LOCAL_CLONE_PATH', './test_repos')).resolve()
                
        self.repo_urls = [url.strip() for url in os.getenv('REPO_URLS', '').split(',') if url.strip()]
        self.repo_type = os.getenv('REPO_TYPE', 'mono')
        self.repo_branch = os.getenv('REPO_BRANCH', 'main')
        # Store repos in pipelinev2/repos directory
        self.local_path = self.base_dir / os.getenv('LOCAL_CLONE_PATH', 'repos')
        self.git_username = os.getenv('GIT_USERNAME')
        self.git_token = os.getenv('GIT_TOKEN')
        
        # Initialize OpenAI LLM
        model = 'gpt-4o'
        self.llm = get_open_ai(temperature=0.3, model=model)
        logger.info(f"Initialized OpenAI LLM with model: {model}")

        self.memory_context = memory_context


    def _handle_rate_limit(self, retry_after: int):
        """Handle rate limit by sleeping for the specified duration."""
        logger.warning(f"Rate limit hit. Waiting for {retry_after} seconds before retrying...")
        time.sleep(retry_after)

    def _make_llm_call(self, messages: List[dict], max_retries: int = 3) -> str:
        """Make LLM call with rate limit handling."""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = self.llm.invoke(messages)
                return response.content
            except Exception as e:
                error_str = str(e)
                if "429" in error_str:  # Rate limit hit
                    retry_after = 2  # Default to 2 seconds if not specified
                    if "retry-after" in error_str.lower():
                        try:
                            # Try to extract retry-after value
                            retry_after = int(error_str.split("retry-after:")[1].split()[0])
                        except:
                            pass
                    self._handle_rate_limit(retry_after)
                    retry_count += 1
                else:
                    raise e
        
        raise Exception(f"Failed after {max_retries} retries due to rate limits")

    def _initialize_git_repo(self, path: Path) -> None:
        """Initialize a git repository if it doesn't exist."""
        try:
            # Check if .git directory exists
            git_dir = path / ".git"
            if not git_dir.exists():
                logger.info(f"Initializing new git repository in {path}")
                repo = git.Repo.init(path)
                
                # Set git config
                with repo.config_writer() as git_config:
                    git_config.set_value('user', 'name', 'forge-bot')
                    git_config.set_value('user', 'email', 'forge-bot@example.com')
                
                # Create .gitignore if it doesn't exist
                gitignore_path = path / ".gitignore"
                if not gitignore_path.exists():
                    with open(gitignore_path, 'w') as f:
                        f.write("*.pyc\n__pycache__/\n.env\n.vscode/\n")
                
                # Initial commit
                repo.index.add(['.gitignore'])
                repo.index.commit("Initial commit")
                
                logger.info("Git repository initialized successfully")
            else:
                logger.info(f"Git repository already exists in {path}")
                
        except Exception as e:
            logger.error(f"Error initializing git repository: {str(e)}")
            raise

    def clone_repositories(self) -> None:
        """Clone the repository/repositories locally."""
        logger.info("Starting repository cloning")
        self.local_path.mkdir(exist_ok=True)
        
        if not self.repo_urls:
            # If no repo URLs provided, initialize a new repo
            self._initialize_git_repo(self.local_path)
            return
                
        if self.repo_type == 'mono':
            self._clone_single_repo(self.repo_urls[0], self.local_path)
        else:
            for repo_url in self.repo_urls:
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                repo_path = self.local_path / repo_name
                self._clone_single_repo(repo_url, repo_path)
        
        logger.info("Repository cloning completed")

    def _clone_single_repo(self, repo_url: str, path: Path) -> None:
        logger.info(f"Cloning repository: {repo_url}")
        
        try:
            if self.git_token:
                _, _, _, owner, repo_name = repo_url.rstrip('.git').split('/')
                auth_url = f"https://{self.git_token}@github.com/{owner}/{repo_name}.git"
            else:
                auth_url = repo_url

            # Check memory context for repo matching
            past_repo = self.memory_context.past_repo_url if self.memory_context else None
            
            if past_repo == repo_url and path.exists():
                try:
                    repo = git.Repo(path)
                    logger.info(f"Existing repository found at {path}, attempting update...")
                    repo.remotes.origin.fetch()
                    repo.git.reset('--hard', f'origin/{self.repo_branch}')
                    
                    with repo.config_writer() as git_config:
                        git_config.set_value('user', 'name', 'forge-bot')
                        git_config.set_value('user', 'email', 'forge-bot@example.com')
                    
                    logger.info("Repository updated successfully")
                    return
                except Exception as e:
                    logger.warning(f"Failed to update repository: {str(e)}")
                    logger.info("Attempting fresh clone...")
                    shutil.rmtree(path)
            elif path.exists():
                logger.info("Different repository detected, removing existing and cloning fresh")
                shutil.rmtree(path)
            
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Cloning repository to: {path}")
            
            # Try main branch first, then master
            for branch in ['main', 'master']:
                try:
                    repo = git.Repo.clone_from(
                        auth_url,
                        path,
                        branch=branch,
                        depth=1
                    )
                    with repo.config_writer() as git_config:
                        git_config.set_value('user', 'name', 'forge-bot')
                        git_config.set_value('user', 'email', 'forge-bot@example.com')
                    logger.info(f"Repository cloned successfully using branch: {branch}")
                    return
                except git.exc.GitCommandError:
                    if branch == 'master':
                        raise
                    logger.warning(f"Failed to clone branch {branch}, trying next branch")
                    if path.exists():
                        shutil.rmtree(path)
                        
        except Exception as e:
            logger.error(f"Error cloning repository: {str(e)}")
            raise

    def generate_file_tree(self, path: Optional[Path] = None) -> Dict:
        """Generate a hierarchical file tree structure with absolute paths."""
        if path is None:
            path = self.local_path

        # Define patterns to exclude
        exclude_patterns = {
            '.git',
            '__pycache__',
            'planning',
            '.env',
            '.vscode',
            '.idea'
        }

        tree = {}
        for item in path.iterdir():
            # Skip excluded directories and files
            if (item.name.startswith('.') or 
                item.name in exclude_patterns or
                'plan_iteration_' in item.name or
                (item.is_file() and item.name in {'plan.json', 'plan.txt'})):
                continue
                
            abs_path = str(item.resolve())  # Get absolute path
            if item.is_file():
                tree[abs_path] = 'file'
            elif item.is_dir():
                tree[abs_path] = self.generate_file_tree(item)
        
        return tree

    def detect_environments(self) -> Dict[str, List[str]]:
        """Detect and analyze different environments in the codebase."""
        logger.info("Detecting environment configurations")
        environments = {
            'development': [],
            'staging': [],
            'production': []
        }

        env_indicators = {
            'development': ['dev', 'development', 'local'],
            'staging': ['staging', 'uat', 'test'],
            'production': ['prod', 'production']
        }

        for root, _, files in os.walk(self.local_path):
            for file in files:
                if file.endswith(('.env', '.yaml', '.yml', '.json')):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(self.local_path)
                    
                    for env, indicators in env_indicators.items():
                        if any(ind in file.lower() for ind in indicators):
                            environments[env].append(str(relative_path))
                            logger.info(f"Found {env} environment file: {relative_path}")

        return environments

    def collect_files_to_analyze(self) -> List[str]:
        """Collect all relevant files for analysis."""
        logger.info("Collecting files for analysis")
        MAX_FILE_SIZE = 50000  # 50KB
        files_to_analyze = []
        
        exclude_patterns = {
            '.git',
            '__pycache__',
            '.pytest_cache',
            '.venv',
            'venv',
            '.env',
            '.idea',
            '.vscode',
            'planning',
            'plan_iteration_',
            'plan.json',
            'plan.txt'
        }
        
        include_extensions = {
            '.tf',
            '.tfvars',
            '.hcl',
            '.yaml',
            '.yml',
            '.json',
            '.sh',
            '.md'
        }
        
        for root, dirs, files in os.walk(self.local_path):
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                if (file.startswith('.') or 
                    any(pattern in root for pattern in exclude_patterns) or
                    any(pattern in file for pattern in exclude_patterns)):
                    continue
                
                if not any(file.endswith(ext) for ext in include_extensions):
                    continue
                
                file_path = os.path.join(root, file)
                
                # Skip large files
                try:
                    if os.path.getsize(file_path) > MAX_FILE_SIZE:
                        logger.warning(f"Skipping large file: {file_path}")
                        continue
                except OSError:
                    continue
                
                files_to_analyze.append(file_path)
                logger.info(f"Added file for analysis: {file_path}")
        
        return files_to_analyze

    def _determine_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension and name"""
        name = file_path.name.lower()
        ext = file_path.suffix.lower()
        
        # Infrastructure as Code
        if ext in ['.tf', '.tfvars']:
            return 'Terraform IaC'
        elif ext in ['.yaml', '.yml'] and any(x in name for x in ['kubernetes', 'k8s']):
            return 'Kubernetes Configuration'
        elif name == 'dockerfile' or ext == '.dockerfile':
            return 'Docker Configuration'
        elif ext in ['.yaml', '.yml'] and 'docker-compose' in name:
            return 'Docker Compose Configuration'
        
        # CI/CD
        elif ext in ['.yaml', '.yml'] and any(x in name for x in ['.github', 'gitlab-ci', 'azure-pipelines']):
            return 'CI/CD Pipeline Configuration'
        
        # Environment Configuration
        elif ext in ['.env', '.conf'] or 'config' in name:
            return 'Environment Configuration'
        
        # Standard Code Files
        elif ext == '.py':
            return 'Python Source'
        elif ext in ['.js', '.ts']:
            return 'JavaScript/TypeScript Source'
        elif ext == '.go':
            return 'Go Source'
        elif ext in ['.java', '.kt']:
            return 'Java/Kotlin Source'
        
        # Documentation
        elif ext in ['.md', '.rst']:
            return 'Documentation'
        
        return f'Generic {ext} file'

    def analyze_file(self, file_path: str, content: str) -> FileAnalysis:
        """Analyze a single file using GPT-4."""
        file_type = self._determine_file_type(Path(file_path))
        logger.info(f"Analyzing file: {file_path}")
        
        # Limit content length
        MAX_CONTENT_LENGTH = 8000
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "..."
        
        prompt = PromptTemplate(
            input_variables=["file_name", "file_type", "content"],
            template=ANALYZE_FILE_TEMPLATE
        )

        try:
            response = self.llm.with_structured_output(FileAnalysis).invoke(
                prompt.format(
                    file_name=os.path.basename(file_path),
                    file_type=file_type,
                    content=content
                )
            )
            
            # Clean up response by removing duplicates
            if hasattr(response, 'patterns'):
                response.patterns = list(set(response.patterns))
            if hasattr(response, 'dependencies'):
                response.dependencies = list(set(response.dependencies))
            
            logger.info(f"Successfully analyzed {file_path}")
            return response
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            return FileAnalysis(
                main_purpose=f"Error analyzing file: {str(e)}",
                key_components=[],
                patterns=[],
                dependencies=[]
            )

    def generate_system_map(self) -> Dict:
        """Generate a complete system map."""
        logger.info("Starting system map generation")
        
        # Check memory context for existing analysis
        if (self.memory_context and 
            self.memory_context.past_repo_url == os.getenv('REPO_URLS') and
            self.memory_context.past_analyses):
            
            logger.info("Using cached analysis from Pinecone")
            return {
                'repository_type': self.repo_type,
                'repository_overview': self.memory_context.past_overview,
                'file_tree': self.generate_file_tree(),
                'file_analyses': self.memory_context.past_analyses,
                'errors': []
            }
        
        # Clone repositories only if needed
        if not (self.memory_context and self.memory_context.past_repo_url == os.getenv('REPO_URLS')):
            self.clone_repositories()
        
        # Generate file tree
        file_tree = self.generate_file_tree()
        logger.info("Generated file tree")
        
        # Detect environments
        environments = self.detect_environments()
        
        # Collect and analyze files
        files_to_analyze = self.collect_files_to_analyze()
        file_analyses = {}
        errors = []
        
        for file_path in files_to_analyze:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                analysis = self.analyze_file(file_path, content)
                file_analyses[file_path] = analysis.dict()
                    
            except Exception as e:
                errors.append(f"Error analyzing {file_path}: {str(e)}")
        
        # Generate repository overview
        repo_overview = self._generate_overview(file_tree, file_analyses)
        
        return {
            'repository_type': self.repo_type,
            'repository_overview': repo_overview,
            'file_tree': file_tree,
            'environments': environments,
            'file_analyses': file_analyses,
            'errors': errors
        }

    def _generate_overview(self, file_tree: Dict, file_analyses: Dict) -> str:
        """Generate repository overview using GPT-4."""
        analyses_str = "\n\n".join([
            f"{path}:\n{json.dumps(analysis, indent=2)}"
            for path, analysis in file_analyses.items()
        ])
        
        # Convert file tree dictionary to string using helper method
        file_structure = self._dict_to_tree_string(file_tree)
        
        # Format the overview prompt using the imported template
        prompt = GENERATE_OVERVIEW_TEMPLATE.format(
            repo_type=self.repo_type,
            file_structure=file_structure,
            analyses_str=analyses_str
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a senior software architect and DevOps expert."),
                HumanMessage(content=prompt)
            ])
            logger.info("Successfully generated repository overview")
            return response.content
        except Exception as e:
            logger.error(f"Error generating overview: {str(e)}")
            return f"Error generating overview: {str(e)}"

    def _dict_to_tree_string(self, tree: Dict, prefix: str = "") -> str:
        """Convert dictionary tree to string representation"""
        result = []
        for key, value in tree.items():
            if isinstance(value, dict):
                result.append(f"{prefix}└── {key}/")
                result.append(self._dict_to_tree_string(value, prefix + "    "))
            else:
                result.append(f"{prefix}└── {key}")
        return "\n".join(result)

    def save_system_map(self, output_dir: str = None) -> None:
        """Save the system map to files."""
        if output_dir is None:
            output_dir = self.system_maps_dir
        else:
            output_dir = Path(output_dir)
            
        logger.info(f"Saving system map to {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate system map if not already done
        system_map = self.generate_system_map()
        
        # Save as JSON
        with open(os.path.join(output_dir, 'system_map.json'), 'w') as f:
            json.dump(system_map, f, indent=2)

def main():
    mapper = SystemMapper()
    mapper.save_system_map()

if __name__ == "__main__":
    main() 