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

VALIDATION_PROMPT = """
Review this implementation plan and the user's clarifications. 
Decide if the plan is ready to be executed.

Original Request:
{query}

Current Plan:
{plan}

User's Existing Answers & Context:
{context}

Return one of three statuses in valid JSON:
{{
  "status": "complete" | "needs_info" | "has_issues",
  "missing_info": [
     {{"question": "...", "context": "...", "default_answer": "..."}}
  ] or null,
  "issue_explanation": "Explanation of issues if has_issues"
}}

Rules:
1. If the plan is fully ready, set "status"="complete".
2. If critical info is missing, set "status"="needs_info" and specify what you absolutely must know.
   Do not re-ask questions if the user has already answered them.
3. If there's a major problem in the plan, set "status"="has_issues" and explain them in "issue_explanation".

Always aim to mark complete unless there's a real blocker.
No repeating or re-asking answered questions. 
"""
