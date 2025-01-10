from typing import TypedDict, List, Union, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
import google.generativeai as genai
import json
import os
from pathlib import Path
from typing import Annotated
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

class FileAnalysis(BaseModel):
    """Schema for file analysis output"""
    main_purpose: str = Field(description="The main purpose and functionality of the file")
    key_components: List[str] = Field(description="Key components, classes, or functions")
    patterns: List[str] = Field(description="Important patterns and architectural decisions")
    devops_relevance: Dict[str, str] = Field(
        description="DevOps-specific aspects of the file",
        default_factory=lambda: {
            "configuration": "None",
            "infrastructure": "None",
            "pipeline": "None",
            "security": "None",
            "monitoring": "None"
        }
    )
    dependencies: List[str] = Field(
        description="External dependencies and integrations",
        default_factory=list
    )

class AnalyzerState(TypedDict):
    messages: Annotated[list, add_messages]
    current_file: Optional[str]
    file_analyses: Dict[str, FileAnalysis]
    repo_overview: Optional[str]
    file_tree: Dict
    repo_type: str
    errors: List[str]

def analyze_file(state: AnalyzerState) -> AnalyzerState:
    """Analyze a single file using GPT-4"""
    if not state["current_file"]:
        return state

    logger.info(f"Analyzing file: {state['current_file']}")
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    
    prompt = PromptTemplate(
        input_variables=["file_name", "file_type", "content"],
        template="""You are a senior software architect and DevOps expert analyzing source code files.
        Analyze the file and provide structured information about its purpose, components, and DevOps relevance.

        File to analyze:
        Name: {file_name}
        Type: {file_type}
        Content: {content}
        
        Provide your analysis in the following structure:
        - Main purpose: Brief description of the file's main purpose
        - Key components: List of key components
        - Patterns: List of important patterns
        - DevOps relevance:
          * Configuration management aspects
          * Infrastructure as Code aspects
          * CI/CD pipeline aspects
          * Security considerations
          * Monitoring/logging setup
        - Dependencies: List of dependencies

        Focus on:
        1. Clear, concise main purpose
        2. Key components and functions
        3. Important patterns and decisions
        4. DevOps relevance in each category
        5. External dependencies and integrations

        Format your response as a structured JSON object matching the FileAnalysis schema."""
    )

    try:
        with open(state["current_file"], 'r', encoding='utf-8') as f:
            content = f.read()
            
        file_type = _determine_file_type(Path(state["current_file"]))
        
        chain = prompt | llm.with_structured_output(FileAnalysis)
        
        result = chain.invoke({
            "file_name": os.path.basename(state["current_file"]),
            "file_type": file_type,
            "content": content
        })
        
        state["file_analyses"][state["current_file"]] = result
        logger.info(f"Successfully analyzed {state['current_file']}")
        
    except Exception as e:
        error_msg = f"Error analyzing file {state['current_file']}: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
    
    return state

def generate_overview(state: AnalyzerState) -> AnalyzerState:
    """Generate repository overview using Gemini Pro"""
    logger.info("Generating repository overview")
    
    try:
        # Initialize Gemini
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        # Convert file analyses to a readable format
        analyses_str = "\n\n".join([
            f"{path}:\n{json.dumps(analysis.dict(), indent=2)}"
            for path, analysis in state["file_analyses"].items()
        ])
        
        prompt = f"""You are a senior software architect and DevOps expert analyzing an entire codebase.
        Generate a comprehensive overview of this {state['repo_type']} repository with focus on architecture, DevOps, and operational aspects.
        
        File Structure:
        {_dict_to_tree_string(state['file_tree'])}
        
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
        
        response = model.generate_content(prompt)
        state["repo_overview"] = response.text
        logger.info("Successfully generated repository overview")
        
    except Exception as e:
        error_msg = f"Error generating repository overview: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
    
    return state

def _determine_file_type(file_path: Path) -> str:
    """Determine file type based on extension and name"""
    name = file_path.name.lower()
    ext = file_path.suffix.lower()
    
    # Infrastructure as Code
    if ext in ['.tf', '.tfvars']:
        return 'Terraform IaC'
    elif ext in ['.yaml', '.yml'] and any(x in name for x in ['kubernetes', 'k8s']):
        return 'Kubernetes Configuration'
    elif name == 'dockerfile' or ext == '.dockerfile':
        return 'Docker Configuration'
    elif ext in ['.yaml', '.yml'] and 'docker-compose' in name:
        return 'Docker Compose Configuration'
    
    # CI/CD
    elif ext in ['.yaml', '.yml'] and any(x in name for x in ['.github', 'gitlab-ci', 'azure-pipelines']):
        return 'CI/CD Pipeline Configuration'
    
    # Environment Configuration
    elif ext in ['.env', '.conf'] or 'config' in name:
        return 'Environment Configuration'
    
    # Standard Code Files
    elif ext == '.py':
        return 'Python Source'
    elif ext in ['.js', '.ts']:
        return 'JavaScript/TypeScript Source'
    elif ext == '.go':
        return 'Go Source'
    elif ext in ['.java', '.kt']:
        return 'Java/Kotlin Source'
    
    # Documentation
    elif ext in ['.md', '.rst']:
        return 'Documentation'
    
    return f'Generic {ext} file'

def _dict_to_tree_string(tree: Dict, prefix: str = "") -> str:
    """Convert dictionary tree to string representation"""
    result = []
    for key, value in tree.items():
        if isinstance(value, dict):
            result.append(f"{prefix}└── {key}/")
            result.append(_dict_to_tree_string(value, prefix + "    "))
        else:
            result.append(f"{prefix}└── {key}")
    return "\n".join(result)

def create_analyzer_workflow():
    """Create the analyzer workflow"""
    workflow = StateGraph(AnalyzerState)
    
    # Add nodes for file analysis and overview generation
    workflow.add_node("analyze_file", analyze_file)
    workflow.add_node("generate_overview", generate_overview)
    
    # Set entry point
    workflow.set_entry_point("analyze_file")
    
    # Add edges
    workflow.add_edge("analyze_file", "generate_overview")
    workflow.add_edge("generate_overview", END)
    
    return workflow.compile()

def analyze_codebase(
    files: List[str],
    file_tree: Dict,
    repo_type: str = "mono"
) -> Dict:
    """Start the codebase analysis process"""
    workflow = create_analyzer_workflow()
    
    # Initialize state
    initial_state = AnalyzerState({
        "messages": [],
        "current_file": None,
        "file_analyses": {},
        "repo_overview": None,
        "file_tree": file_tree,
        "repo_type": repo_type,
        "errors": []
    })
    
    # Process each file
    final_state = initial_state
    for file in files:
        final_state["current_file"] = file
        final_state = workflow.invoke(final_state)
    
    return {
        "file_analyses": {k: v.dict() for k, v in final_state["file_analyses"].items()},
        "repo_overview": final_state["repo_overview"],
        "errors": final_state["errors"]
    }