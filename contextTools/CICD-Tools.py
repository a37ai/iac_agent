"""
CI/CD Pipelines – Data Retrieval & Summarization

--------------------------------------------------------------------------------
CREDENTIALS & CONFIGURATION REQUIRED:

1. Jenkins:
   Typically, you have:
     {
         "jenkins_url": "https://jenkins.example.com",
         "username": "myuser",         # or service account
         "api_token": "my-api-token",
         "verify_ssl": True            # optional, default True
     }
   The script uses Basic Auth to query Jenkins JSON API endpoints. It fetches an overview
   of jobs, build statuses, and pipeline info.

2. GitLab CI/CD:
   - Provide:
     {
         "gitlab_url": "https://gitlab.example.com",  # or "https://gitlab.com"
         "private_token": "my-personal-access-token",
         "verify_ssl": True
     }
   The script queries GitLab’s REST API for project pipelines, jobs, statuses, etc.

3. GitHub Actions:
   - Provide:
     {
         "github_api_url": "https://api.github.com",  # normally https://api.github.com
         "owner": "my-org-or-username",
         "repo": "my-repo",
         "personal_access_token": "ghp_XXXX",
         "verify_ssl": True
     }
   The script queries the GitHub REST API for Actions workflows and runs.

4. CircleCI:
   - Provide:
     {
         "circleci_api_url": "https://circleci.com/api/v2",
         "personal_token": "circleci-token-XXXX",
         "project_slug": "gh/my-org/my-repo",
         "verify_ssl": True
     }
   The script queries CircleCI’s API v2 for pipelines/workflows in the specified project.

5. Gemini LLM API Key:
   - A valid API key for Google's Generative AI service (Gemini). Provide as a string.
     e.g. GEMINI_API_KEY = "your-api-key"

--------------------------------------------------------------------------------
"""

import json
import os
import requests
from typing import Dict, Any

# For Google Generative AI (Gemini)
import google.generativeai as genai


###############################################################################
# Utility: Configure Gemini & Summarization
###############################################################################

def configure_llm(api_key: str):
    """
    Configure the Google Generative AI client to use the specified API key.
    """
    genai.configure(api_key=api_key)


def summarize_with_llm(
    model_name: str,
    raw_data: str,
    prompt_instructions: str
) -> str:
    """
    Send raw data and instructions to the specified Gemini model, returning a summary.

    :param model_name: The Gemini model name, e.g. "models/gemini-1.5-pro".
    :param raw_data: A string containing raw data to be summarized.
    :param prompt_instructions: Instructions appended to the raw data for summarization.
    :return: LLM-generated summary text.
    """
    model = genai.GenerativeModel(model_name)
    prompt = f"{prompt_instructions}\n\n--- RAW DATA START ---\n{raw_data}\n--- RAW DATA END ---\n"
    response = model.generate_content(prompt)
    return response.text


###############################################################################
# 1. Jenkins – Data Retrieval & Summarization
###############################################################################

def fetch_jenkins_data(
    jenkins_url: str,
    username: str,
    api_token: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from a Jenkins server using Basic Auth with user + API token.
    Typical data:
      - List of jobs (and their last build statuses)
      - Possibly pipeline details (e.g., stages) if using Jenkins pipelines.

    :param jenkins_url: Base URL of Jenkins, e.g. "https://jenkins.example.com".
    :param username: Jenkins username or service account.
    :param api_token: Jenkins API token.
    :param verify_ssl: Whether to verify SSL certs for HTTPS.
    :return: A dictionary containing job info and minimal build data.
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.auth = (username, api_token)

    # Fetch top-level Jenkins info (includes a list of jobs)
    main_url = f"{jenkins_url}/api/json"
    resp = session.get(main_url)
    resp.raise_for_status()
    data = resp.json()

    # For each job, get more details
    job_details = []
    for job in data.get("jobs", []):
        job_url = f"{job['url']}api/json"
        job_resp = session.get(job_url)
        job_resp.raise_for_status()
        job_data = job_resp.json()

        # Grab last build info (if any)
        last_build_info = {}
        if job_data.get("lastBuild"):
            last_build_url = f"{job_data['lastBuild']['url']}api/json"
            lb_resp = session.get(last_build_url)
            lb_resp.raise_for_status()
            last_build_info = lb_resp.json()

        job_details.append({
            "name": job.get("name"),
            "color": job_data.get("color"),  # often "blue", "red", "yellow" for success, fail, unstable
            "description": job_data.get("description"),
            "last_build": {
                "number": last_build_info.get("number"),
                "status": last_build_info.get("result"),
                "duration": last_build_info.get("duration"),
            } if last_build_info else None
        })

    return {
        "jenkins_version": data.get("version"),
        "jobs_count": len(job_details),
        "jobs": job_details
    }


def summarize_jenkins_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize Jenkins data using Gemini.

    :param credentials: Dict with 'jenkins_url', 'username', 'api_token', 'verify_ssl'.
    :param api_key: Gemini API key.
    :param model_name: Which Gemini model to use.
    :return: Summarized text of Jenkins resources.
    """
    # 1. Fetch Jenkins data
    jenkins_data = fetch_jenkins_data(
        jenkins_url=credentials["jenkins_url"],
        username=credentials["username"],
        api_token=credentials["api_token"],
        verify_ssl=credentials.get("verify_ssl", True),
    )

    # 2. Convert to JSON
    jenkins_data_str = json.dumps(jenkins_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for Jenkins. Provide a concise but comprehensive summary of:\n"
        "• Jenkins version (if available)\n"
        "• Jobs (names, last build status)\n"
        "• Notable failures or job anomalies\n"
        "Offer insights into potential improvements or issues."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, jenkins_data_str, prompt_instructions)
    return summary


###############################################################################
# 2. GitLab CI/CD – Data Retrieval & Summarization
###############################################################################

def fetch_gitlab_data(
    gitlab_url: str,
    private_token: str,
    verify_ssl: bool = True,
    projects_limit: int = 5
) -> Dict[str, Any]:
    """
    Fetch data from GitLab, such as projects and their recent pipelines.
    This is a basic example using the GitLab REST API.

    :param gitlab_url: Base URL for GitLab, e.g. "https://gitlab.com".
    :param private_token: A GitLab personal access token.
    :param verify_ssl: Whether to verify SSL certificates.
    :param projects_limit: How many projects to fetch (for brevity).
    :return: Dictionary of structured GitLab data.
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.headers.update({"Private-Token": private_token})

    # Get current user info (optional)
    user_url = f"{gitlab_url}/api/v4/user"
    user_resp = session.get(user_url)
    user_resp.raise_for_status()
    user_data = user_resp.json()

    # Get list of projects for this user (limited for brevity)
    projects_url = f"{gitlab_url}/api/v4/projects?membership=true&order_by=last_activity_at&per_page={projects_limit}"
    proj_resp = session.get(projects_url)
    proj_resp.raise_for_status()
    projects_data = proj_resp.json()

    # For each project, gather some pipeline info
    projects_details = []
    for proj in projects_data:
        project_id = proj["id"]
        pipelines_endpoint = f"{gitlab_url}/api/v4/projects/{project_id}/pipelines?per_page=3"
        pipe_resp = session.get(pipelines_endpoint)
        pipe_resp.raise_for_status()
        pipeline_data = pipe_resp.json()  # recent 3 pipelines

        projects_details.append({
            "name": proj["name"],
            "path_with_namespace": proj["path_with_namespace"],
            "visibility": proj["visibility"],
            "web_url": proj["web_url"],
            "recent_pipelines": pipeline_data
        })

    return {
        "current_user": user_data.get("username"),
        "projects_count": len(projects_details),
        "projects": projects_details
    }


def summarize_gitlab_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize GitLab CI/CD data using Gemini.

    :param credentials: Dict with 'gitlab_url', 'private_token', 'verify_ssl'.
    :param api_key: Gemini API key.
    :param model_name: The Gemini model to use.
    :return: Summarized text of GitLab CI/CD resources.
    """
    # 1. Fetch GitLab data
    gitlab_data = fetch_gitlab_data(
        gitlab_url=credentials["gitlab_url"],
        private_token=credentials["private_token"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert to JSON
    gitlab_data_str = json.dumps(gitlab_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for GitLab CI/CD. Provide a concise summary of:\n"
        "• Current user info\n"
        "• Projects (visibility, recent pipelines)\n"
        "• Pipeline statuses or any notable failures\n"
        "Offer insights on potential improvements or anomalies."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, gitlab_data_str, prompt_instructions)
    return summary


###############################################################################
# 3. GitHub Actions – Data Retrieval & Summarization
###############################################################################

def fetch_github_actions_data(
    github_api_url: str,
    owner: str,
    repo: str,
    personal_access_token: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from GitHub Actions, such as workflows and recent runs.

    :param github_api_url: Base GitHub API URL (usually "https://api.github.com").
    :param owner: Repository owner (username or org).
    :param repo: Repository name.
    :param personal_access_token: Personal access token with repo/workflow scope.
    :param verify_ssl: Whether to verify SSL certs.
    :return: A dictionary of GitHub Actions workflows and runs info.
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.headers.update({"Authorization": f"Bearer {personal_access_token}"})

    # Fetch workflows
    workflows_url = f"{github_api_url}/repos/{owner}/{repo}/actions/workflows"
    wf_resp = session.get(workflows_url)
    wf_resp.raise_for_status()
    workflows_data = wf_resp.json()

    # For each workflow, fetch recent runs
    all_workflows_details = []
    for wf in workflows_data.get("workflows", []):
        runs_url = f"{github_api_url}/repos/{owner}/{repo}/actions/workflows/{wf['id']}/runs?per_page=3"
        runs_resp = session.get(runs_url)
        runs_resp.raise_for_status()
        runs_data = runs_resp.json()

        all_workflows_details.append({
            "workflow_name": wf.get("name"),
            "workflow_id": wf.get("id"),
            "state": wf.get("state"),  # active or disabled
            "recent_runs": runs_data.get("workflow_runs", [])
        })

    return {
        "repository": f"{owner}/{repo}",
        "workflows_count": len(all_workflows_details),
        "workflows": all_workflows_details
    }


def summarize_github_actions_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize GitHub Actions data using Gemini.

    :param credentials: Dict with "github_api_url", "owner", "repo", "personal_access_token".
    :param api_key: Gemini API key.
    :param model_name: The Gemini model to use.
    :return: Summarized text of GitHub Actions workflows and runs.
    """
    # 1. Fetch GitHub Actions data
    gh_data = fetch_github_actions_data(
        github_api_url=credentials["github_api_url"],
        owner=credentials["owner"],
        repo=credentials["repo"],
        personal_access_token=credentials["personal_access_token"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert to JSON
    gh_data_str = json.dumps(gh_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for GitHub Actions. Provide a concise summary that covers:\n"
        "• Workflows (names, whether active)\n"
        "• Recent runs (success/fail, statuses)\n"
        "Highlight any anomalies, frequent failures, or potential improvements."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, gh_data_str, prompt_instructions)
    return summary


###############################################################################
# 4. CircleCI – Data Retrieval & Summarization
###############################################################################

def fetch_circleci_data(
    circleci_api_url: str,
    personal_token: str,
    project_slug: str,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Fetch data from CircleCI's API v2, e.g. pipelines for a given project slug.

    :param circleci_api_url: Typically "https://circleci.com/api/v2".
    :param personal_token: CircleCI personal API token.
    :param project_slug: e.g. "gh/yourorg/yourrepo" or "bitbucket/..."
    :param verify_ssl: Whether to verify SSL certs.
    :return: Dictionary of CircleCI project pipeline data.
    """
    session = requests.Session()
    session.verify = verify_ssl
    session.headers.update({"Circle-Token": personal_token})

    # Fetch recent pipelines for the project
    pipelines_url = f"{circleci_api_url}/project/{project_slug}/pipeline?limit=5"
    pipe_resp = session.get(pipelines_url)
    pipe_resp.raise_for_status()
    pipelines_data = pipe_resp.json()

    # For each pipeline, fetch its workflows
    pipelines_details = []
    for pipeline in pipelines_data.get("items", []):
        pipeline_id = pipeline.get("id")
        workflow_url = f"{circleci_api_url}/pipeline/{pipeline_id}/workflow"
        wf_resp = session.get(workflow_url)
        wf_resp.raise_for_status()
        workflow_data = wf_resp.json()

        pipelines_details.append({
            "id": pipeline_id,
            "state": pipeline.get("state"),
            "number": pipeline.get("number"),
            "created_at": pipeline.get("created_at"),
            "workflows": workflow_data.get("items", [])
        })

    return {
        "project_slug": project_slug,
        "pipeline_count": len(pipelines_details),
        "pipelines": pipelines_details
    }


def summarize_circleci_data(
    credentials: Dict[str, Any],
    api_key: str,
    model_name: str = "models/gemini-1.5-pro"
) -> str:
    """
    Summarize CircleCI data using Gemini.

    :param credentials: Dict with 'circleci_api_url', 'personal_token', 'project_slug', 'verify_ssl'.
    :param api_key: Gemini API key.
    :param model_name: The Gemini model to use.
    :return: Summarized text of CircleCI pipelines and workflows.
    """
    # 1. Fetch data from CircleCI
    circle_data = fetch_circleci_data(
        circleci_api_url=credentials["circleci_api_url"],
        personal_token=credentials["personal_token"],
        project_slug=credentials["project_slug"],
        verify_ssl=credentials.get("verify_ssl", True)
    )

    # 2. Convert to JSON
    circle_data_str = json.dumps(circle_data, indent=2)

    # 3. Configure LLM
    configure_llm(api_key)

    # 4. Prompt instructions
    prompt_instructions = (
        "You are an expert summarizer for CircleCI pipelines. Provide a concise summary covering:\n"
        "• Recent pipelines (state, number, created_at)\n"
        "• Workflows (status, any notable failures)\n"
        "Highlight unusual or error-prone pipelines and suggest improvements."
    )

    # 5. Summarize
    summary = summarize_with_llm(model_name, circle_data_str, prompt_instructions)
    return summary


###############################################################################
# 5. Example Main
###############################################################################

if __name__ == "__main__":
    # Jenkins Credentials
    jenkins_credentials = {
        "jenkins_url": "https://jenkins.example.com",
        "username": "myuser",
        "api_token": "my-jenkins-token",
        "verify_ssl": True
    }

    # GitLab Credentials
    gitlab_credentials = {
        "gitlab_url": "https://gitlab.com",
        "private_token": "my-gitlab-token",
        "verify_ssl": True
    }

    # GitHub Actions Credentials
    github_credentials = {
        "github_api_url": "https://api.github.com",
        "owner": "my-org",
        "repo": "my-repo",
        "personal_access_token": "ghp_myGithubPAT",
        "verify_ssl": True
    }

    # CircleCI Credentials
    circleci_credentials = {
        "circleci_api_url": "https://circleci.com/api/v2",
        "personal_token": "my-circleci-token",
        "project_slug": "gh/my-org/my-repo",
        "verify_ssl": True
    }

    # Replace with your actual Gemini API key
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "dummy-api-key")

    # Summarize Jenkins Data
    print("===== JENKINS SUMMARY =====")
    jenkins_summary = summarize_jenkins_data(jenkins_credentials, GEMINI_API_KEY)
    print(jenkins_summary)
    print()

    # Summarize GitLab Data
    print("===== GITLAB SUMMARY =====")
    gitlab_summary = summarize_gitlab_data(gitlab_credentials, GEMINI_API_KEY)
    print(gitlab_summary)
    print()

    # Summarize GitHub Actions Data
    print("===== GITHUB ACTIONS SUMMARY =====")
    github_summary = summarize_github_actions_data(github_credentials, GEMINI_API_KEY)
    print(github_summary)
    print()

    # Summarize CircleCI Data
    print("===== CIRCLECI SUMMARY =====")
    circleci_summary = summarize_circleci_data(circleci_credentials, GEMINI_API_KEY)
    print(circleci_summary)
