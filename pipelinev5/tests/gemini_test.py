# test_gemini.py
import os
from ai_models.gemini_models import GeminiJSONModel
from typing import TypedDict, Optional, List, Dict
from pathlib import Path

test_file = Path("test_repos/credits.md")
with open(test_file, 'r', encoding='utf-8') as f:
   test_content = f.read()

sample_prompt = """You must analyze this file and return a JSON object with this exact schema:

{{
    "main_purpose": "string",
    "key_components": ["string"],
    "patterns": ["string"],
    "devops_relevance": {{
        "configuration": "string",
        "infrastructure": "string",
        "pipeline": "string",
        "security": "string",
        "monitoring": "string"
    }},
    "dependencies": ["string"]
}}

File content: {content}
"""

def main():
    model = GeminiJSONModel(temperature=0.3, model="gemini-1.5-pro")
    response = model.invoke([
        {"content": "You are a software analyst."},
        {"content": sample_prompt.format(content=test_content)}
    ])
    print(response.content)


if __name__ == "__main__":
    main()