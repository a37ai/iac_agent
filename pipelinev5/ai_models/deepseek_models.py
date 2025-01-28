from langchain_openai.chat_models.base import BaseChatOpenAI
from utils.general_helper_functions import load_config
import os
# from dotenv import load_dotenv

# load_dotenv()
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

deepseek_api_key = os.getenv('DEEPSEEK_API_KEY', 'your-deepseek-api-key')
# os.environ["DEEPSEEK_API_KEY"] = deepseek_api_key

langmith_api_key = os.getenv('LANGSMITH_API_KEY', 'your_LANGCHAIN_PROJECT')
os.environ["LANGSMITH_API_KEY"] = langmith_api_key

langchain_tracing_v2 = os.getenv('LANGCHAIN_TRACING_V2', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_TRACING_V2"] = langchain_tracing_v2

langchain_endpoint = os.getenv('LANGCHAIN_ENDPOINT', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_ENDPOINT"] = langchain_endpoint

langchain_project = os.getenv('LANGCHAIN_PROJECT', 'your_LANGCHAIN_PROJECT')
os.environ["LANGCHAIN_PROJECT"] = langchain_project

def get_deepseek_ai(temperature=0, model='deepseek-reasoner'):
    llm = BaseChatOpenAI(
    api_key = deepseek_api_key,
    model=model,
    temperature = temperature,
    openai_api_base='https://api.deepseek.com',
    max_tokens=8192
)
    return llm

def get_deepseek_ai_json(temperature=0, model='deepseek-reasoner'):
    llm = BaseChatOpenAI(
    model=model,
    api_key = deepseek_api_key,
    temperature = temperature,
    openai_api_base='https://api.deepseek.com',
    max_tokens=8192,
    model_kwargs={"response_format": {"type": "json_object"}},
)
    return llm
