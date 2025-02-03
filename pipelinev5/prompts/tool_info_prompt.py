
TOOL_INFO_PROMPT = """You are an assistant that identifies references to known DevOps integration tools from a user query. 

Known tools:
{tools}

User query:
---
{query}
---

Instructions:
1. Determine if the user query references any tool from the known tools list (case-insensitive).
2. Return a JSON object using the following schema (without markdown or additional text):

{{
  "tool_name": "<name_of_the_tool_or_none>",
  "reasoning": "<short_reasoning_here>"
}}

Examples:
---
If the query references "aws," respond:
{{
  "tool_name": "aws",
  "reasoning": "User specifically mentioned AWS."
}}

If the query references none of the known tools, respond:
{{
  "tool_name": "none",
  "reasoning": "No references found in the user query."
}}
"""