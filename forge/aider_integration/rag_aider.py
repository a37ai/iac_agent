"""
RAG-enhanced Aider chat interface.
Extends Aider's capabilities with documentation-aware responses.
"""
from typing import Optional, Dict, Any, List
import logging
from pathlib import Path

from aider.io import InputOutput
from aider.coders import Coder
from aider.commands import Command

from ..rag_retriever import RAGRetriever
from ..rag_llm import RAGLLMPipeline
from ..rag_coder import RAGCodeGenerator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGAiderCommand(Command):
    """Command that integrates RAG capabilities into Aider"""
    
    name = "rag"
    help = "Use RAG system to get documentation-aware responses"
    
    def __init__(self, coder: Coder):
        super().__init__(coder)
        self.docs_dir = Path("docs")
        self.retriever = RAGRetriever(docs_dir=str(self.docs_dir))
        self.pipeline = RAGLLMPipeline(retriever=self.retriever)
        self.generator = RAGCodeGenerator(pipeline=self.pipeline)
    
    async def run(self, args: str) -> bool:
        """Run the RAG command with given arguments"""
        try:
            # Process the query through RAG pipeline
            response = await self.pipeline.process_query(args)
            
            # Format and display the response
            self.coder.io.tool_output(
                f"\nTool: {response['tool']}\n"
                f"Category: {response['category']}\n"
                f"Answer: {response['answer']}\n"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error in RAG command: {str(e)}")
            self.coder.io.tool_error(f"Error: {str(e)}")
            return False

class RAGAiderCoder(Coder):
    """Extended Aider Coder with RAG capabilities"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize RAG components
        self.docs_dir = Path("docs")
        self.retriever = RAGRetriever(docs_dir=str(self.docs_dir))
        self.pipeline = RAGLLMPipeline(retriever=self.retriever)
        self.generator = RAGCodeGenerator(pipeline=self.pipeline)
        
        # Register RAG command
        self.commands['rag'] = RAGAiderCommand(self)
    
    async def get_chat_response(self, prompt: str) -> str:
        """Enhanced chat response that includes RAG context"""
        try:
            # Get documentation context
            response = await self.pipeline.process_query(prompt)
            
            # Add documentation context to the prompt
            enhanced_prompt = (
                f"Based on the following documentation context:\n\n"
                f"Tool: {response['tool']}\n"
                f"Category: {response['category']}\n"
                f"{response['answer']}\n\n"
                f"User query: {prompt}"
            )
            
            # Get response from parent class
            return await super().get_chat_response(enhanced_prompt)
            
        except Exception as e:
            logger.error(f"Error getting RAG-enhanced response: {str(e)}")
            return await super().get_chat_response(prompt)  # Fallback to normal response
