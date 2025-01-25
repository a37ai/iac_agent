# pipelinev5/agent_tools/github_tools.py

import os
import requests
from typing import List, Optional, Dict, Any
from termcolor import colored
from states.state import ToolResult
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

github_token = os.getenv("GIT_TOKEN")

def fetch_github(owner: str, repo: str, endpoint: str, method: str = "GET", params: dict = None) -> Dict[str, Any]:
    """
    Generic GitHub API request handler with error handling
    """
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(colored(f"GitHub API error: {str(e)}", 'red'))
        return {"error": str(e)}

class GitHubTools:
    """Collection of GitHub API tools."""
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        
    def fetch_issues(self, state: str = "all") -> ToolResult:
        """Fetch repository issues."""
        try:
            params = {"state": state}
            result = fetch_github(self.owner, self.repo, "issues", params=params)
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching issues: {str(e)}"
            )

    def fetch_branches(self) -> ToolResult:
        """Fetch repository branches."""
        try:
            result = fetch_github(self.owner, self.repo, "branches")
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching branches: {str(e)}"
            )

    def fetch_pull_requests(self, state: str = "all") -> ToolResult:
        """Fetch repository pull requests."""
        try:
            params = {"state": state}
            result = fetch_github(self.owner, self.repo, "pulls", params=params)
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching pull requests: {str(e)}"
            )

    def fetch_releases(self) -> ToolResult:
        """Fetch repository releases."""
        try:
            result = fetch_github(self.owner, self.repo, "releases")
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching releases: {str(e)}"
            )

    def fetch_commits(self, sha: Optional[str] = None) -> ToolResult:
        """Fetch repository commits."""
        try:
            endpoint = f"commits{f'/{sha}' if sha else ''}"
            result = fetch_github(self.owner, self.repo, endpoint)
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching commits: {str(e)}"
            )

    def fetch_collaborators(self) -> ToolResult:
        """Fetch repository collaborators."""
        try:
            result = fetch_github(self.owner, self.repo, "collaborators")
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching collaborators: {str(e)}"
            )

    def fetch_deployments(self) -> ToolResult:
        """Fetch repository deployments."""
        try:
            result = fetch_github(self.owner, self.repo, "deployments")
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching deployments: {str(e)}"
            )

    def fetch_workflow_runs(self, workflow_id: Optional[str] = None) -> ToolResult:
        """Fetch repository workflow runs."""
        try:
            endpoint = f"actions/runs{f'/{workflow_id}' if workflow_id else ''}"
            result = fetch_github(self.owner, self.repo, endpoint)
            
            if "error" in result:
                return ToolResult(
                    status="error",
                    error=result["error"]
                )
                
            return ToolResult(
                status="success",
                output=str(result)
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                error=f"Error fetching workflow runs: {str(e)}"
            )