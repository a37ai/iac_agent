planning_prompt = """
You are a DevOps expert creating an implementation plan.

Query: {query}

Codebase Overview:
{codebase_overview}

Repository Structure:
{file_tree}

File Analysis:
{file_analyses}

You must return a JSON object with this exact schema:
{{
    "steps": [
        {{
            "description": "Clear description of what needs to be done",
            "content": "Specific changes or commands to execute",
            "step_type": "code" | "command",
            "files": ["list", "of", "files"] 
        }},
        {{
            "description": "Clear description of what needs to be done",
            "content": "Specific changes or commands to execute",
            "step_type": "code" | "command",
            "files": ["list", "of", "files"]
        }}
    ]
}}

Requirements for each field:
- description: A clear, actionable description of the step
- content: 
  - For "code" steps, include the exact code changes
  - For "command" steps, the exact command to run
- step_type: Must be either "code" or "command"
- files: 
  - For code steps, list all relevant files to edit
  - For command steps, use an empty list if no files are modified

Create a **complete** implementation plan that maintains consistency with the existing codebase.

Additionally, the user has provided these clarifications/answers to previous questions:
{answers}

In your plan, you **must** respect and incorporate these user answers. 
**Do not** re-ask or repeat any question whose answer is already provided.
"""
