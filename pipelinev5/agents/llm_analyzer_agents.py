import os
import json
import google.generativeai as genai
from typing import TypedDict, List, Union, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pathlib import Path
from utils.general_helper_functions import configure_logger
from states.state import AnalyzerState, FileAnalysis
from utils.logging_helper_functions import initialize_logging, log_interaction, log_status_update
from prompts.llm_analyzer_prompts import ANALYZE_FILE_PROMPT, OVERVIEW_PROMPT
from ai_models.openai_models import get_open_ai
from agent_tools.llm_analyzer_tools import _determine_file_type, _dict_to_tree_string

logger = configure_logger(__name__)

def analyze_file(state: AnalyzerState) -> AnalyzerState:
    """Analyze a single file using GPT-4"""
    if not state["current_file"]:
        return state

    logger.info(f"Analyzing file: {state['current_file']}")
    
    llm = get_open_ai(temperature=0.3, model='gpt-4o')
    
    prompt = PromptTemplate(
        input_variables=["file_name", "file_type", "content"],
        template=ANALYZE_FILE_PROMPT
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
        
        prompt = OVERVIEW_PROMPT.format(
            repo_type=state['repo_type'],
            file_tree=_dict_to_tree_string(state['file_tree']),
            analyses_str=analyses_str
        )
        
        response = model.generate_content(prompt)
        state["repo_overview"] = response.text
        logger.info("Successfully generated repository overview")
        
    except Exception as e:
        error_msg = f"Error generating repository overview: {str(e)}"
        logger.error(error_msg)
        state["errors"].append(error_msg)
    
    return state

