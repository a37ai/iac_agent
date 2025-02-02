from langchain_openai.chat_models.base import BaseChatOpenAI
from utils.general_helper_functions import load_config
import os
from langchain_groq import ChatGroq
from langchain_core.callbacks import StreamingStdOutCallbackHandler



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


def get_deepseek_groq(
    temperature=0.6,
    model="deepseek-r1-distill-llama-70b",
    streaming=True,
    max_tokens=1024
):
    """
    Initialize a standard Groq DeepSeek chat model.
    
    Args:
        temperature (float): Controls randomness in responses (0.0-2.0)
        model (str): Model identifier
        streaming (bool): Whether to enable response streaming
        max_tokens (int): Maximum length of model's response
        top_p (float): Controls diversity of token selection (0.0-1.0)
        seed (int, optional): Set for reproducible results
        reasoning_format (str): Controls how model reasoning is presented ("parsed", "raw", "hidden")
    
    Returns:
        ChatGroq: Configured chat model instance
    """
    callbacks = [StreamingStdOutCallbackHandler()] if streaming else None
    
    return ChatGroq(
        model_name=model,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        callbacks=callbacks,
    )

def get_deepseek_groq_json(
    temperature=0.6,
    model="deepseek-r1-distill-llama-70b",
    streaming=False,  # Default to False for JSON mode
    max_tokens=1024,
):
    """
    Initialize a Groq DeepSeek chat model with JSON output mode.
    
    Args:
        temperature (float): Controls randomness in responses (0.0-2.0)
        model (str): Model identifier
        streaming (bool): Whether to enable response streaming
        max_tokens (int): Maximum length of model's response
        top_p (float): Controls diversity of token selection (0.0-1.0)
        seed (int, optional): Set for reproducible results
        reasoning_format (str): Controls how model reasoning is presented ("parsed", "raw", "hidden")
    
    Returns:
        ChatGroq: Configured chat model instance with JSON output
    """
    callbacks = [StreamingStdOutCallbackHandler()] if streaming else None
    
    return ChatGroq(
        model_name=model,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        callbacks=callbacks,
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
    )