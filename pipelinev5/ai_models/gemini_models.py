import requests
import json
import os
from utils.general_helper_functions import load_config
from langchain_core.messages.human import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

class GeminiJSONModel:
    def __init__(self, temperature=0, model=None):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
        load_config(config_path)
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.headers = {
            'Content-Type': 'application/json'
        }
        self.model_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        self.temperature = temperature
        self.model = model

    def invoke(self, messages):
        system = messages[0]["content"]
        user = messages[1]["content"]

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"system:{system}. Your output must be JSON formatted. Just return the specified JSON format, do not prepend your response with anything.\n\nuser:{user}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": self.temperature
            },
        }

        try:
            request_response = requests.post(
                self.model_endpoint, 
                headers=self.headers, 
                data=json.dumps(payload)
            )
            
            print("REQUEST RESPONSE", request_response.status_code)
            # print("\n\nREQUEST RESPONSE HEADERS", request_response.headers)
            # print("\n\nREQUEST RESPONSE TEXT", request_response.text)
            
            request_response_json = request_response.json()

            if 'candidates' not in request_response_json or not request_response_json['candidates']:
                raise ValueError("No content in response")

            response_content = request_response_json['candidates'][0]['content']['parts'][0]['text']
            
            response = json.loads(response_content)
            response = json.dumps(response)

            response_formatted = HumanMessage(content=response)

            return response_formatted
        except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as e:
            error_message = f"Error in invoking model! {str(e)}"
            print("ERROR", error_message)
            response = {"error": error_message}
            response_formatted = HumanMessage(content=json.dumps(response))
            return response_formatted

class GeminiModel:
    def __init__(self, temperature=0, model=None):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
        load_config(config_path)
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.headers = {
            'Content-Type': 'application/json'
        }
        self.model_endpoint = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={self.api_key}"
        self.temperature = temperature
        self.model = model

    def invoke(self, messages):
        system = messages[0]["content"]
        user = messages[1]["content"]

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"system:{system}\n\nuser:{user}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature
            },
        }

        try:
            request_response = requests.post(
                self.model_endpoint, 
                headers=self.headers, 
                data=json.dumps(payload)
            )
            
            print("REQUEST RESPONSE", request_response.status_code)
            
            request_response_json = request_response.json()

            if 'candidates' not in request_response_json or not request_response_json['candidates']:
                raise ValueError("No content in response")

            response_content = request_response_json['candidates'][0]['content']['parts'][0]['text']
            response_formatted = HumanMessage(content=response_content)

            return response_formatted
        except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as e:
            error_message = f"Error in invoking model! {str(e)}"
            print("ERROR", error_message)
            response = {"error": error_message}
            response_formatted = HumanMessage(content=json.dumps(response))
            return response_formatted


# class GeminiJSONModel:
#     def __init__(self, temperature=0, model=None):
#         self.llm = ChatGoogleGenerativeAI(
#             model=model,
#             temperature=temperature,
#             google_api_key=os.getenv("GOOGLE_API_KEY"),
#             convert_system_message_to_human=True
#         )

#     def invoke(self, messages):
#         system_msg = messages[0]["content"] + ". Your output must be JSON formatted. Just return the specified JSON format, do not prepend your response with anything."
#         messages[0]["content"] = system_msg
#         response = self.llm.invoke(messages)
#         return HumanMessage(content=json.dumps(json.loads(response.content)))

# class GeminiModel:
#     def __init__(self, temperature=0, model=None):
#         self.llm = ChatGoogleGenerativeAI(
#             model=model,
#             temperature=temperature,
#             google_api_key=os.getenv("GOOGLE_API_KEY"),
#             convert_system_message_to_human=True
#         )

#     def invoke(self, messages):
#         response = self.llm.invoke(messages)
#         return HumanMessage(content=response.content)