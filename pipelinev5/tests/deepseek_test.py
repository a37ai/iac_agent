from langchain_openai.chat_models.base import BaseChatOpenAI
from langchain_openai import ChatOpenAI
import os
from ai_models.deepseek_models import get_deepseek_ai

llm = get_deepseek_ai()
response = llm.invoke("What is 2+2? Answer in one word.")
print(response.content)


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