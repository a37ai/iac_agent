import json
from termcolor import colored
from langchain_core.messages import SystemMessage
from ai_models.openai_models import get_open_ai_json
from states.state import AgentGraphState
from agent_tools.github_tools import GitHubTools
from prompts.github_agent_prompts import github_agent_prompt

def github_agent(state: AgentGraphState, model=None, server=None) -> AgentGraphState:
    """
    GitHub agent that retrieves relevant information from GitHub based on the query.
    """
    try:
        print(colored("\nGitHub Agent 🐙: Starting analysis...", 'cyan'))
        
        # Initialize GitHub tools
        github_tools = GitHubTools(
            owner=state.get("github_owner", ""),
            repo=state.get("github_repo", "")
        )
        
        # Format the GitHub prompt
        prompt = github_agent_prompt.format(
            owner=state.get("github_owner", ""),
            repo=state.get("github_repo", "")
        )

        print(f"Owner: {state.get('github_owner', '')}")
        print(f"repo: {state.get('github_repo', '')}")

        # Format context for LLM
        context = {
            "query": state["query"],
            "github_owner": state.get("github_owner", ""),
            "github_repo": state.get("github_repo", ""),
            "available_tools": [
                "fetch_issues",
                "fetch_branches",
                "fetch_pull_requests",
                "fetch_releases",
                "fetch_commits",
                "fetch_collaborators",
                "fetch_deployments",
                "fetch_workflow_runs"
            ]
        }

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(context)}
        ]

        # Get LLM decision about which tools to use
        if server == 'openai':
            llm = get_open_ai_json(model=model)
        
        print(colored("GitHub Agent 🐙: Determining required information...", 'cyan'))
        ai_msg = llm.invoke(messages)
        
        try:
            # Clean and parse the response
            response_str = ai_msg.content.strip()
            # Remove any leading/trailing whitespace or quotes
            if response_str.startswith('"'):
                response_str = response_str[1:]
            if response_str.endswith('"'):
                response_str = response_str[:-1]
            
            # Parse the cleaned JSON
            decision = json.loads(response_str)
            
            # Validate required fields
            required_fields = ["tools_to_use", "focus_areas", "rationale"]
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field: {field}")
            
            if not isinstance(decision["tools_to_use"], list):
                raise ValueError("tools_to_use must be a list")
            
            print(colored(f"GitHub Agent 🐙: Will fetch: {', '.join(decision['tools_to_use'])}", 'cyan'))
            print(colored(f"Rationale: {decision['rationale']}", 'cyan'))
                
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response from LLM: {str(e)}\nResponse was: {response_str}"
            print(colored(error_msg, 'red'))
            raise
        except ValueError as e:
            error_msg = f"Invalid response format: {str(e)}\nResponse was: {response_str}"
            print(colored(error_msg, 'red'))
            raise
        
        # Initialize github_info structure
        github_info = {
            "metadata": {
                "focus_areas": decision.get("focus_areas", []),
                "rationale": decision.get("rationale", ""),
                "tools_used": decision.get("tools_to_use", [])
            },
            "data": {}
        }

        # Execute each requested tool and store results
        for tool_name in decision.get("tools_to_use", []):
            print(colored(f"\nGitHub Agent 🐙: Fetching {tool_name}...", 'cyan'))
            
            tool_func = getattr(github_tools, tool_name, None)
            if tool_func:
                try:
                    result = tool_func()
                    
                    if result.status == "success":
                        # Try to parse the output string as JSON if it looks like JSON
                        try:
                            if isinstance(result.output, str) and (
                                result.output.strip().startswith('{') or 
                                result.output.strip().startswith('[')
                            ):
                                parsed_output = json.loads(result.output)
                                github_info["data"][tool_name] = parsed_output
                            else:
                                github_info["data"][tool_name] = result.output
                        except json.JSONDecodeError:
                            github_info["data"][tool_name] = result.output
                        
                        print(colored(f"✓ Successfully retrieved {tool_name}", 'green'))
                    else:
                        error_msg = f"Failed to fetch {tool_name}: {result.error}"
                        github_info["data"][tool_name] = {"error": error_msg}
                        print(colored(f"✗ {error_msg}", 'red'))
                except Exception as e:
                    error_msg = f"Error executing {tool_name}: {str(e)}"
                    github_info["data"][tool_name] = {"error": error_msg}
                    print(colored(f"✗ {error_msg}", 'red'))
            else:
                error_msg = f"Tool {tool_name} not found"
                github_info["data"][tool_name] = {"error": error_msg}
                print(colored(f"✗ {error_msg}", 'red'))

        # Format collected information into a structured string
        formatted_info = []
        formatted_info.append("GitHub Analysis Results:")
        formatted_info.append(f"\nFocus Areas: {', '.join(github_info['metadata']['focus_areas'])}")
        formatted_info.append(f"Rationale: {github_info['metadata']['rationale']}\n")
        
        for tool_name, data in github_info["data"].items():
            formatted_info.append(f"\n{tool_name.replace('fetch_', '').title()}:")
            if isinstance(data, dict) and "error" in data:
                formatted_info.append(f"Error: {data['error']}")
            else:
                # Format the data more readably
                if isinstance(data, (dict, list)):
                    formatted_data = json.dumps(data, indent=2)
                    formatted_info.append(formatted_data)
                else:
                    formatted_info.append(str(data))

        # Store the formatted string in state
        state["github_info"] = "\n".join(formatted_info)
        
        # Store raw data and response for logging
        if "github_agent_response" not in state:
            state["github_agent_response"] = []
        state["github_agent_response"].append(
            SystemMessage(content=json.dumps({
                "decision": decision,
                "github_info": github_info
            }))
        )
        
        print(colored("\nGitHub Agent 🐙: Analysis complete", 'green'))
        return state

    except Exception as e:
        error_msg = f"Error in github_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        if "github_agent_response" not in state:
            state["github_agent_response"] = []
        state["github_agent_response"].append(SystemMessage(content=error_msg))
        return state