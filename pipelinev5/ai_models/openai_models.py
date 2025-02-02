from langchain_openai import ChatOpenAI
from utils.general_helper_functions import load_config
import os
# from dotenv import load_dotenv
from langchain.chat_models.base import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import List, Optional, Any, Dict
from openai import OpenAI
from pydantic import Field
    
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

def get_open_ai_json_v2(model='o3-mini'):

    class CustomChatModel(BaseChatModel):
        model_name: str = Field(..., description="Name of the model to use")
        model_kwargs: Dict = Field(default_factory=dict, description="Kwargs for the model")
        client: Any = Field(default_factory=lambda: OpenAI(), exclude=True)

        def _generate(self, 
                    messages: List[Any], 
                    stop: Optional[List[str]] = None,
                    run_manager = None,
                    **kwargs) -> ChatResult:
            role_map = {
                "human": "user",
                "ai": "assistant",
                "system": "system"
            }

            openai_messages = [
                {
                    "role": role_map[msg.type],
                    "content": msg.content
                }
                for msg in messages
            ]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=openai_messages,
                **self.model_kwargs
            )

            message_content = response.choices[0].message.content
            generation = ChatGeneration(message=AIMessage(content=message_content))
            
            return ChatResult(generations=[generation])

        @property
        def _llm_type(self) -> str:
            return "openai_chat_model"

    return CustomChatModel(
        model_name=model,
        model_kwargs={"response_format": {"type": "json_object"}}
    )