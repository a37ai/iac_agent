import os
from dotenv import load_dotenv
from langchain.chat_models.base import BaseChatModel
from utils.general_helper_functions import load_config
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from typing import List, Optional, Any, Dict
from openai import OpenAI
from pydantic import Field
from utils.general_helper_functions import load_config
import os
# from dotenv import load_dotenv

# load_dotenv()
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

class CustomChatModel(BaseChatModel):
    model_name: str = Field(..., description="Name of the model to use")
    model_kwargs: Dict = Field(default_factory=dict, description="Kwargs for the model")
    client: Any = Field(default_factory=lambda: OpenAI(), exclude=True)

    def _generate(self, 
                 messages: List[Any], 
                 stop: Optional[List[str]] = None,
                 run_manager = None,
                 **kwargs) -> ChatResult:
        # Map LangChain message types to OpenAI roles
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

# Initialize the chat model
chat = CustomChatModel(
    model_name="o3-mini",
    model_kwargs={"response_format": {"type": "json_object"}}
)

# Sample analysis prompt for structured output
analysis_prompt = """Analyze this code snippet and return a JSON object containing:
- main_function: the primary function name
- parameters: list of parameters
- purpose: brief description of what it does
- complexity: estimated time complexity

Code:
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr"""

messages = [
    SystemMessage(content="You are an AI that responds with structured JSON data."),
    HumanMessage(content=analysis_prompt)
]

response = chat.invoke(messages)
print("\nCode Analysis Response:")
print(response.content)

# Try another example
person_prompt = """Please analyze the following person's information and return it in a structured JSON format.
Include their name, occupation, skills, and a brief bio.

Person: John Smith is a software engineer with 5 years of experience in Python and JavaScript. 
He specializes in backend development and has worked on several machine learning projects."""

messages2 = [
    SystemMessage(content="You are an AI that responds with structured JSON data."),
    HumanMessage(content=person_prompt)
]

response2 = chat.invoke(messages2)
print("\nPerson Analysis Response:")
print(response2.content)