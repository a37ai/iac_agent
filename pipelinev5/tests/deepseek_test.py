from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_openai import ChatOpenAI
import os
from ai_models.deepseek_models import get_deepseek_ai
from groq import Groq
from utils.general_helper_functions import load_config
from langchain_groq import ChatGroq
from langchain_core.callbacks import StreamingStdOutCallbackHandler
from langchain_core.messages import HumanMessage

# load_dotenv()
config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

os.getenv("GROQ_API_KEY", "your-groq-api-key")

# llm = get_deepseek_ai()
# response = llm.invoke("What is 2+2? Answer in one word.")
# print(response.content)


# from openai import OpenAI
# import os

# deepseek_api_key = "sk-bfefcd5f8a194fff9f78af60429c0f41"
# client = OpenAI(api_key="deepseek_api_key", base_url="https://api.deepseek.com")

# response = client.chat.completions.create(
#     model="deepseek-chat",
#     messages=[
#         {"role": "system", "content": "You are a helpful assistant"},
#         {"role": "user", "content": "Hello"},
#     ],
#     stream=False
# )

# print(response.choices[0].message.content)

# Initialize the chat model with streaming
chat = ChatGroq(
    model_name="deepseek-r1-distill-llama-70b",
    temperature=0.6,
    max_tokens=1024,
    # streaming=True,
    # callbacks=[StreamingStdOutCallbackHandler()],
    model_kwargs={"response_format": {"type": "json_object"}},
    reasoning_format="hidden"
)

def test_chat():
    # Test message
    message = HumanMessage(content="How many r's are in the word strawberry? json {{number_of_r's: 3}}")

    response = chat.invoke([message])
    
    # Print the full response (optional since we're already streaming)
    print("\nFull response:", response.content)

if __name__ == "__main__":
    test_chat()