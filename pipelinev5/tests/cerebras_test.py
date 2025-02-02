import os
from cerebras.cloud.sdk import Cerebras
from utils.general_helper_functions import load_config
import os
# from dotenv import load_dotenv

# load_dotenv()
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

# client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

# client.models.list()
# client.models.retrieve("llama3.1-8b")


# try:
#     client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))
    
#     print("Available Models:")
#     print("-" * 50)
#     models = client.models.list()
    
#     for model in models.data:
#         print(f"Model ID: {model.id}")
#         print(f"Owner: {model.owned_by}")
#         print(f"Object Type: {model.object}")
#         print("-" * 50)
        
# except Exception as e:
#     print(f"An error occurred: {str(e)}")


# client = Cerebras(
#   api_key=os.environ.get("CEREBRAS_API_KEY"),
# )

# chat_completion = client.chat.completions.create(
#   messages=[
#   {"role": "user", "content": "Why is fast inference important?",}
# ],
#   model="deepseek-r1-distill-llama-70b",
# )

import os
from langchain_cerebras import ChatCerebras
import json
from typing import List, Dict

def create_test_messages() -> List[Dict[str, str]]:
    test_context = {
        "query": "Create a Python script to process CSV files",
        "codebase_overview": "Simple Python project",
        "file_tree": "project/\n  ├── src/\n  └── tests/",
        "file_analyses": "Sample file analyses",
        "answers": {},
        "github_info": "",
        "validation_feedback": "No validation issues to address.",
        "os": "darwin"
    }
    
    # Fixed prompt with proper string formatting
    test_prompt = '''You are an AI assistant that creates implementation plans.
Based on the provided context, create a detailed plan and format your response as a JSON object with the following structure:
{{
    "steps": [
        {{
            "step_number": 1,
            "description": "Description of the step",
            "code_changes": ["List of code changes needed"],
            "validation_criteria": ["List of validation criteria"]
        }}
    ]
}}

Context: {query}'''
    
    return [
        {"role": "system", "content": test_prompt.format(**test_context)},
        {"role": "user", "content": json.dumps(test_context)}
    ]

def test_cerebras_chat():
    try:
        # Initialize the model with correct parameter placement
        llm = ChatCerebras(
            model="llama-3.3-70b",
            temperature=0.7,
            max_tokens=2000,
            top_p=1,
            model_kwargs={
                "response_format": {"type": "json_object"}
            }
        )
        
        # Create test messages
        messages = create_test_messages()
        
        print("Sending request to Cerebras API...")
        print("Messages being sent:", json.dumps(messages, indent=2))
        
        # Make the API call
        response = llm.invoke(messages)
        
        print("\nResponse received:")
        print(f"Response type: {type(response)}")
        print(f"Response content: {response.content}")
        
        # Try parsing the JSON response
        try:
            parsed_response = json.loads(response.content)
            print("\nParsed JSON response:")
            print(json.dumps(parsed_response, indent=2))
        except json.JSONDecodeError as e:
            print(f"\nFailed to parse response as JSON: {e}")
        
        return response
        
    except Exception as e:
        print(f"Error in test_cerebras_chat: {str(e)}")
        raise

if __name__ == "__main__":
    # Make sure you have your API key set
    cerebras_api_key = os.getenv('CEREBRAS_API_KEY')
    if not cerebras_api_key:
        raise ValueError("CEREBRAS_API_KEY environment variable is not set")
    
    print(f"API Key present (first 5 chars): {cerebras_api_key[:5]}...")
    
    # Run the test
    test_cerebras_chat()