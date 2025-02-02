replanning_prompt_template = """You are a DevOps expert modifying an implementation plan based on user feedback.

Edit Request:
{edit_request}

The user is on {os} OS.

Original Plan:
{original_plan}

Codebase Overview:
{codebase_overview}

Repository Structure:
{file_tree}

File Analysis:
{file_analyses}

Create an updated plan that incorporates the requested changes while maintaining consistency with the codebase.

You must return a JSON object with this exact schema:
{{
    "steps": [
        {{
            "description": "Clear description of what needs to be done",
            "content": "Specific changes or commands to execute",
            "step_type": "code" | "command",
            "files": ["list", "of", "files"] // empty list for command steps
        }}
    ]
}}

Requirements for each field:
- description: Clear, actionable description of the step
- content: For code steps, include the exact code changes. For command steps, the exact command to run
- step_type: Must be either "code" or "command"
- files: For code steps, list all files that will be modified. For command steps, use empty list

Return the complete updated plan, not just the changes. Ensure all steps are properly sequenced and maintain dependencies.""" 