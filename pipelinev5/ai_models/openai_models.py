from langchain_openai import ChatOpenAI
from utils.general_helper_functions import load_config
import os
# from dotenv import load_dotenv

# load_dotenv()
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

openai_api_key = os.getenv('OPENAI_API_KEY', 'your-openai-api-key')
os.environ["OPENAI_API_KEY"] = openai_api_key

langmith_api_key = os.getenv('LANGSMITH_API_KEY', 'your_LANGCHAIN_PROJECT')
os.environ["LANGSMITH_API_KEY"] = langmith_api_key

langchain_tracing_v2 = os.getenv('LANGCHAIN_TRACING_V2', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_TRACING_V2"] = langchain_tracing_v2

langchain_endpoint = os.getenv('LANGCHAIN_ENDPOINT', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_ENDPOINT"] = langchain_endpoint

langchain_project = os.getenv('LANGCHAIN_PROJECT', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_PROJECT"] = langchain_project



def get_open_ai(temperature=0, model='gpt-4o'):
    llm = ChatOpenAI(
    model=model,
    temperature = temperature,
)
    return llm

def get_open_ai_json(temperature=0, model='gpt-4o'):
    llm = ChatOpenAI(
    model=model,
    temperature = temperature,
    model_kwargs={"response_format": {"type": "json_object"}},
)
    return llm
