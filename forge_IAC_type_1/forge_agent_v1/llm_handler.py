import os
import json
import logging
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from .models import (
    forgeQuestions,
    UserQuestions,
    TaskDecomposition,
    Tests,
    applyCommands,  
    Commands,
    UserQuestion,
    forgeQuery,
    errorQuery,     
)
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class LLMHandler:
    def __init__(self, repo_path: str):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.6,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.repo_path = Path(repo_path)
        # Configure structured output using JSON mode
        self.structured_llm = self.llm.with_structured_output(forgeQuestions, method="json_mode")
        self.query_llm = self.llm.with_structured_output(forgeQuery, method="json_mode")
        self.user_questions_llm = self.llm.with_structured_output(UserQuestions, method="json_mode")
        self.decomposition_llm = self.llm.with_structured_output(TaskDecomposition, method="json_mode")
        self.test_functions_llm = self.llm.with_structured_output(Tests, method="json_mode")
        self.apply_functions_llm = self.llm.with_structured_output(Commands, method="json_mode")
        self.error_query_llm = self.llm.with_structured_output(errorQuery, method="json_mode")
        self.response_llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

    def generate_test_functions(self, original_query: str, forge_query: str) -> List[str]:
        prompt = PromptTemplate(
            template="""
            You are an expert Infrastructure as Code (IaC) developer. Your end user gave you a task to implement the following query: {original_query}.
             
            You added specifics to the query to better understand the user's request: {forge_query}.

            You are now tasked with generating test functions (CLI commands) to test the implementation of the user's request. 
             
            These commands will be run prior to applying the changes to the infrastructure.  
            
            For example, if terraform is being used, you can use terraform validate, terraform plan. If you use "terraform plan", make sure output the plan to a file in the command.Dont include commands that apply the changes to the infrastructure. Dont include commands that destroy the infrastructure. Dont include commands that are not related to testing the IaC. Dont include commands that query the infrastructure, since its not even applied yet.

            **Output Format:**

            Return a JSON object with a single key "tests", where "tests" is a list of test descriptions.

            **Example Output:**

            ```json
            {{
                "tests": [
                    {{
                        "test": "terraform init"
                    }},
                    {{
                        "test": "terraform validate"
                    }},
                    {{
                        "test": "terraform plan"
                    }}
                ]
            }}
            ```
            """,
            input_variables=["original_query", "forge_query"]
        )

        try:
            print("Invoking test functions LLM")
            response = self.test_functions_llm.invoke(
                prompt.format(
                    original_query=original_query,
                    forge_query=forge_query,
                )
            )
            print(f"LLM response: {response}")
            logger.debug(f"Generated LLM response: {response}")
            return response.tests
        except Exception as e:
            logger.error(f"Failed to generate response using LLM: {e}")
            raise
    
    def generate_apply_functions(self, forge_query: str, ran_tests: str) -> List[str]:
        prompt = PromptTemplate(
            template="""
            You are an expert Infrastructure as Code (IaC) developer.

            You have already implemented the user's request: {forge_query}.

            You ran the following tests on the codebase: {ran_tests}. They all ran successfully.

            Now you are tasked with generating CLI commands to apply the changes to the infrastructure. 

            **Output Format:**

            Return a JSON object with a single key "commands", where "commands" is a list of CLI commands to apply the changes to the infrastructure.

            **Example Output:**

            ```json
            {{
                "commands": [
                    {{
                        "command": "terraform apply"
                    }},
                ]
            }}
            ```
            """,
            input_variables=["forge_query", "ran_tests"]
        )

        try:
            print("Invoking test functions LLM")
            response = self.apply_functions_llm.invoke(
                prompt.format(
                    forge_query=forge_query,
                    ran_tests=ran_tests,
                )
            )
            print(f"LLM response: {response}")
            logger.debug(f"Generated LLM response: {response}")
            return response.commands
        except Exception as e:
            logger.error(f"Failed to generate response using LLM: {e}")
            raise
    

    def generate_forge_query(self, user_query: str, user_responses: List[dict]) -> str:
        formatted_user_responses = [
            {
                "question": resp['question']['question'],
                "response": resp['response']
            } for resp in user_responses
        ]
        prompt = f"""
        You are an expert developer acting as a copilot. Your job is to generate a detailed task description for forge, an AI coding agent, to implement the user's request and update the codebase accordingly. Base your task description on the user's request and their answers to specific questions.

        User's Request:
        "{user_query}"

        User's Answers:
        {json.dumps(formatted_user_responses, indent=2)}

        Provide a clear and actionable task description for forge to execute.

        **Output Format:**

        Return a JSON object with a single key "task", where "task" is the task description.

        **Example Output:**

        ```json
        {{
            "task": "Create a new virtual network with specified subnets and security groups as per user requirements."
        }}
        ```
        """

        try:
            print("Invoking forge query LLM")
            response = self.query_llm.invoke(prompt)
            print(f"LLM response: {response}")
            logger.debug(f"Generated LLM response: {response}")
            return response.task.strip()
        except Exception as e:
            logger.error(f"Failed to generate response using LLM: {e}")
            raise

    def generate_user_questions(self, user_query: str) -> List[UserQuestion]:
        try:
            prompt = PromptTemplate(
                template="""
                You are an expert Infrastructure as Code (IaC) developer acting as a copilot. Your job is to generate specific questions that need to be answered by the user before implementing their request.

                User's Query: {user_query}

                Based on the specific query, generate questions that will help clarify any ambiguities or gather necessary details to proceed.

                **Output Format:**

                Return a JSON object with a single key `"questions"`, which is a list of question objects. Each question object should have the following keys:
                - `question`: The specific question to ask.
                - `context`: Important context that helps the user understand why this question matters.
                - `default`: A reasonable default answer as a string (use JSON-formatted strings for complex values).

                Generate up to 3 questions, focusing on the most critical information needed.

                **Example Output:**

                ```json
                {{
                    "questions": [
                        {{
                            "question": "Which cloud provider should the infrastructure be deployed to?",
                            "context": "Different cloud providers have specific configurations and services.",
                            "default": "AWS"
                        }},
                        {{
                            "question": "Do you have any naming conventions for resources?",
                            "context": "Consistent naming helps in resource management and identification.",
                            "default": "project-name-resource-type"
                        }}
                    ]
                }}
                ```
                """,
                input_variables=["user_query"]
            )

            response = self.user_questions_llm.invoke(
                prompt.format(
                    user_query=user_query,
                )
            )

            logger.debug(f"Generated user questions: {response}")

            if not response.questions:
                logger.warning("No questions were generated!")
                # Provide some default questions as fallback
                return [
                    UserQuestion(
                        question="Can you provide more details about the infrastructure you want to implement?",
                        context="Detailed requirements help in accurate implementation.",
                        default="No additional details."
                    )
                ]

            return response.questions

        except Exception as e:
            logger.error(f"Failed to generate user questions: {str(e)}")
            raise

    def generate_error_query(self, starting_query) -> str:
        try:
            prompt = f"""
            {starting_query}

            Please respond in a JSON format with a 'query' key. Example:

            ```json
            {{
                "query": "Provide guidance or corrective actions for the error described."
            }}
            ```
            """

            response = self.error_query_llm.invoke(prompt)
            logger.debug(f"Generated LLM response: {response}")
            return response.query.strip()
        except Exception as e:
            print(f"Failed to generate response using LLM: {e}")
            logger.error(f"Failed to generate response using LLM: {e}")
            raise
