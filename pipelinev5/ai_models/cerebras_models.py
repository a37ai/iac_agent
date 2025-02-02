import os
from utils.general_helper_functions import load_config
from langchain_cerebras import ChatCerebras

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

cerebras_api_key = os.getenv('CEREBRAS_API_KEY', 'your-cerebras-api-key')
os.environ["CEREBRAS_API_KEY"] = cerebras_api_key

langmith_api_key = os.getenv('LANGSMITH_API_KEY', 'your_LANGCHAIN_PROJECT')
os.environ["LANGSMITH_API_KEY"] = langmith_api_key

langchain_tracing_v2 = os.getenv('LANGCHAIN_TRACING_V2', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_TRACING_V2"] = langchain_tracing_v2

langchain_endpoint = os.getenv('LANGCHAIN_ENDPOINT', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_ENDPOINT"] = langchain_endpoint

langchain_project = os.getenv('LANGCHAIN_PROJECT', 'your_LANGCHAIN_PROJECT')

def get_cerebras_json():
    llm = ChatCerebras(
        model="llama-3.3-70b",
        temperature=0.7,
        max_tokens=2000,
        top_p=1,
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
    )
    return llm
    
