# prompts/tools_prompts.py

from langchain_core.prompts import PromptTemplate

# Template for strict JSON response validation via LLM
LLM_VALIDATION_TEMPLATE = """You are a helpful AI that must analyze the given query 
and produce a strict JSON response in the format:
{{
"valid": "YES" or "NO",
"explanation": "string explaining why"
}}

Context to analyze:
{context}
"""
