planning_prompt_template = """
You are a DevOps expert creating an implementation plan.

Query: {query}

Codebase Overview:
{codebase_overview}

Repository Structure:
{file_tree}

File Analysis:
{file_analyses}

Previous answers from the user:
{answers}

{validation_feedback}

You must return a JSON object with this exact schema:
{{
    "steps": [
        {{
            "description": "Clear description of what needs to be done",
            "content": "Specific changes or commands to execute",
            "step_type": "code" | "command",
            "files": ["list", "of", "files"] 
        }}
    ]
}}

Requirements:
- description: A clear, actionable description of the step
- content: Exact code changes or commands
- step_type: Must be "code" or "command"
- files: List relevant files or empty list for commands

Create a complete implementation plan that:
1. Maintains consistency with existing codebase
2. Incorporates all user answers
3. Has clear, specific steps
4. Includes all necessary file paths
5. Addresses any validation issues mentioned above
"""

planning_prompt_template_with_github = """
You are a DevOps expert creating an implementation plan.

Query: {query}

Codebase Overview:
{codebase_overview}

Repository Structure:
{file_tree}

File Analysis:
{file_analyses}

GitHub Context:
{github_info}

Previous answers from the user:
{answers}

{validation_feedback}

You must return a JSON object with this exact schema:
{{
    "steps": [
        {{
            "description": "Clear description of what needs to be done",
            "content": "Specific changes or commands to execute",
            "step_type": "code" | "command",
            "files": ["list", "of", "files"] 
        }}
    ]
}}

Requirements:
- description: A clear, actionable description of the step
- content: Exact code changes or commands
- step_type: Must be "code" or "command"
- files: List relevant files or empty list for commands

Create a complete implementation plan that:
1. Maintains consistency with existing codebase
2. Incorporates all user answers
3. Aligns with GitHub context
4. Has clear, specific steps
5. Includes all necessary file paths
6. Addresses any validation issues mentioned above
"""

validation_prompt_template = """
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

validation_prompt_template_with_github = """
Review this implementation plan and the user's clarifications. 
Decide if the plan is ready to be executed.

Original Request:
{query}

Current Plan:
{plan}

User's Existing Answers & Context:
{context}

GitHub Context:
{github_info}

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

When GitHub information is present, also verify:
- Plan properly addresses any referenced issues or PRs
- Steps are compatible with current branch states
- No conflicts with active workflows or deployments
- Steps follow repository conventions and patterns
- Required permissions and access are available

Always aim to mark complete unless there's a real blocker.
No repeating or re-asking answered questions. 
"""

question_generator_prompt_template_with_github = """
You are a DevOps expert. The user has asked:
{query}

So far, the user has provided the following clarifications:
{answers}

Codebase overview:
{codebase_overview}

GitHub Context:
{github_info}

Consider if you need clarification about:
- Specific issues or PRs being referenced
- Target branches for changes
- Required repository permissions
- CI/CD workflow requirements
- Repository-specific conventions

If there's clarifications you need to make the plan more complete, ask now.
Generate a list of questions that will help you create a more complete plan.
If you need to clarification and all given information is clear, return an empty "questions" list.

Return your response in valid JSON with exactly this structure:
{{
  "questions": [
    {{
      "question": "...",
      "context": "Why we need it",
      "default_answer": "A recommended default"
    }}
  ]
}}

If no questions are needed, return:
{{
  "questions": []
}}
"""


question_generator_prompt_template = """
You are a DevOps expert. The user has asked:
{query}

So far, the user has provided the following clarifications:
{answers}

Codebase overview:
{codebase_overview}

If there's clarifications you need to make the plan more complete, ask now.
Generate a list of questions that will help you create a more complete plan.
If you need to clarification and all given information is clear, return an empty "questions" list.

Return your response in valid JSON with exactly this structure:
{{
  "questions": [
    {{
      "question": "...",
      "context": "Why we need it",
      "default_answer": "A recommended default"
    }}
  ]
}}

If no questions are needed, return:
{{
  "questions": []
}}
"""
        
QUESTION_WITH_ADDITIONAL_CONTEXT_PROMPT = """
{base_prompt}

Additional context from validation:
{issues_context}

Missing info from validation (if any):
{missing_info}
"""

QUESTION_WITH_ADDITIONAL_CONTEXT_PROMPT_WITH_GITHUB = """
{base_prompt}

Additional context from validation:
{issues_context}

GitHub Context:
{github_info}

Missing info from validation (if any):
{missing_info}
"""