# prompts/system_mapper_prompts.py

from langchain_core.prompts import PromptTemplate

# Prompt template for analyzing a single file
ANALYZE_FILE_TEMPLATE = """You are a senior software architect and DevOps expert analyzing source code files.
Analyze the file and provide structured information about its purpose, components, and DevOps relevance.

File to analyze:
Name: {file_name}
Type: {file_type}
Content: {content}

Focus on:
1. Clear, concise main purpose
2. Key components and functions
3. Important patterns and decisions
4. DevOps relevance in each category
5. External dependencies and integrations"""

# Prompt template for generating repository overview
GENERATE_OVERVIEW_TEMPLATE = """You are a senior software architect and DevOps expert analyzing an entire codebase.
Generate a comprehensive overview of this {repo_type} repository with focus on architecture, DevOps, and operational aspects.

File Structure:
{file_structure}

Detailed File Analyses:
{analyses_str}

Provide a detailed analysis covering:

1. Overall Architecture
- High-level system design
- Design patterns and principles
- System boundaries and interfaces

2. Development Infrastructure
- Technology stack
- Key dependencies
- Development tools and requirements

3. DevOps Infrastructure
- Deployment architecture
- Infrastructure as Code setup
- Configuration management approach
- Service dependencies and integration points

4. Environment Management
- Development, staging, and production environments
- Environment-specific configurations
- Environment promotion strategy
- Configuration and secret management

5. CI/CD Pipeline
- Build and deployment processes
- Testing strategies
- Deployment strategies (blue-green, canary, etc.)
- Release management

6. Operational Considerations
- Monitoring and logging setup
- Security measures
- Scalability provisions
- Backup and disaster recovery

7. Areas for Improvement
- Technical debt
- Security considerations
- Scalability concerns
- DevOps pipeline optimization

Format your response in clear sections with markdown headings."""
