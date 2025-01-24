"""
Interface for LLM integration in the RAG pipeline.
"""
import os
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv, find_dotenv
import json
from openai import AsyncOpenAI
from typing import Optional, Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMInterface:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        """Initialize the LLM interface"""
        self.model = model
        # Force reload environment variables
        dotenv_path = find_dotenv()
        logger.info(f"Found .env file at: {dotenv_path}")
        load_dotenv(dotenv_path, override=True)
        
        # Debug: print all environment variables
        for key, value in os.environ.items():
            if 'key' in key.lower():
                logger.info(f"Environment variable {key}: {value[:10]}...")
                
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
        # Ensure API key is set
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable must be set")
        self.api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"Final OpenAI API key: {self.api_key[:10]}...")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=4))
    async def generate_completion(self, 
                                prompt: str,
                                temperature: float = 0.7,
                                max_tokens: int = 1000) -> str:
        """Generate completion from the LLM"""
        try:
            # Create a new client for each request
            client = AsyncOpenAI(api_key=self.api_key)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a DevOps expert assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in LLM completion: {e}")
            raise

    async def analyze_query(self, query: str) -> Dict[str, str]:
        """Analyze a query to determine relevant documentation"""
        try:
            # Create a new client for each request to ensure we use the latest API key
            client = AsyncOpenAI(api_key=self.api_key)
            
            prompt = f"""Analyze this DevOps query to determine the relevant tool and category.
            Query: {query}
            
            Respond with a JSON object containing:
            - tool: The primary DevOps tool being asked about (e.g., terraform, ansible, docker)
            - category: The category of the query (e.g., configuration, deployment, monitoring)
            """
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # Parse the response
            content = response.choices[0].message.content
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {content}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in LLM query analysis: {e}")
            return {}
            
    async def generate_answer(self, query: str, context: str) -> str:
        """Generate an answer using the LLM"""
        try:
            # Create a new client for each request to ensure we use the latest API key
            client = AsyncOpenAI(api_key=self.api_key)
            
            prompt = f"""You are a helpful DevOps assistant. Using the provided documentation, answer the user's query.
            
            Documentation:
            {context}
            
            Query: {query}
            
            Provide a clear and concise answer, focusing on practical steps and best practices.
            """
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in LLM answer generation: {e}")
            return f"Error generating answer: {str(e)}"
