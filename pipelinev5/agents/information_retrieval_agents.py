import json
import os
from langchain_core.messages import SystemMessage
from states.state import AgentGraphState
from termcolor import colored
import requests
from datetime import datetime
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

def documentation_agent(state: AgentGraphState, model=None, server=None) -> AgentGraphState:
    """
    Documentation agent that retrieves information based on the documentation query
    using the Perplexity API.
    """
    try:
        # Initialize documentation response list if not present
        if "documentation_agent_response" not in state:
            state["documentation_agent_response"] = []
            
        # Initialize retrieved_documentation if not present
        if "retrieved_documentation" not in state:
            state["retrieved_documentation"] = []

        # # Debug: Print state at start
        # print(colored("\nDebug - Documentation Agent - Initial state:", 'yellow'))
        # print(colored(f"needs_documentation: {state.get('needs_documentation')}", 'yellow'))
        # print(colored(f"documentation_query: {state.get('documentation_query')}", 'yellow'))
        # print(colored(f"Total docs retrieved: {len(state.get('retrieved_documentation', []))}", 'yellow'))

        # Get documentation query from state
        query = state.get("documentation_query")
        if not query:
            error_msg = f"No documentation query provided in state. Current docs: {len(state.get('retrieved_documentation', []))}"
            print(colored(error_msg, 'red'))
            state["documentation_agent_response"].append(SystemMessage(content=error_msg))
            return state

        print(colored(f"\nDocumentation Agent 📚: Retrieving information for query: {query}", 'cyan'))

        # Make direct API call to Perplexity
        api_token = os.getenv("PERPLEXITY_API_KEY")
        if not api_token:
            error_msg = "Perplexity API token not found in environment variables"
            print(colored(error_msg, 'red'))
            state["documentation_agent_response"].append(SystemMessage(content=error_msg))
            return state

        api_url = "https://api.perplexity.ai/chat/completions"
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a technical documentation assistant focused on infrastructure, cloud computing, and DevOps. Provide clear, actionable information with specific examples when possible."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": 2000,
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
            response_data = response.json()

            # Extract content from Perplexity response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0]["message"]["content"]
            else:
                raise ValueError("No content found in API response")

            # Create documentation entry with timestamp
            doc_entry = {
                "query": query,
                "info": content,
                "source": "Perplexity API",
                "timestamp": datetime.now().isoformat()
            }

            # Append to retrieved_documentation
            if "retrieved_documentation" not in state:
                state["retrieved_documentation"] = []
            state["retrieved_documentation"].append(doc_entry)

            # Log success
            print(colored("\nDocumentation retrieved successfully ✅", 'green'))
            print(colored("Query:", 'cyan'), query)
            print(colored("Information:", 'cyan'))
            print(content)
            print(colored(f"\nTotal documents retrieved: {len(state['retrieved_documentation'])}", 'green'))

            # Add response to state
            state["documentation_agent_response"].append(
                SystemMessage(content=json.dumps({
                    "status": "success",
                    "documentation": doc_entry
                }))
            )

            # Reset needs_documentation flag but keep the retrieved docs
            state["needs_documentation"] = False
            state["documentation_query"] = None
            
            return state

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            print(colored(error_msg, 'red'))
            state["documentation_agent_response"].append(SystemMessage(content=error_msg))
            return state

        except Exception as e:
            error_msg = f"Error processing API response: {str(e)}"
            print(colored(error_msg, 'red'))
            state["documentation_agent_response"].append(SystemMessage(content=error_msg))
            return state

    except Exception as e:
        error_msg = f"Error in documentation_agent: {str(e)}"
        print(colored(error_msg, 'red'))
        state["documentation_agent_response"].append(SystemMessage(content=error_msg))
        return state