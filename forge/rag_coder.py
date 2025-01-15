"""
Integration of RAG-enhanced LLM pipeline with existing code generation system.
"""
from typing import Optional, Dict, List
from pathlib import Path
import asyncio

from .rag_retriever import DevOpsRetriever
from .rag_llm import RAGLLMPipeline, RAGResponse

class RAGCodeGenerator:
    def __init__(self, docs_dir: str = "docs"):
        """Initialize the RAG-enhanced code generator"""
        self.retriever = DevOpsRetriever(docs_dir)
        self.pipeline = RAGLLMPipeline(self.retriever)
        
    async def generate_code(self, 
                          query: str,
                          error_context: Optional[str] = None,
                          file_context: Optional[Dict[str, str]] = None) -> RAGResponse:
        """
        Generate code using the RAG-enhanced pipeline.
        
        Args:
            query: The code generation query or error message
            error_context: Optional error context if this is error-related
            file_context: Optional dict of relevant file contents
            
        Returns:
            RAGResponse containing the generated code and relevant documentation
        """
        # Build context dictionary
        context = {
            "error_context": error_context,
            "file_context": file_context
        }
        
        # Process through RAG pipeline
        response = await self.pipeline.process_query(query, context)
        return response
    
    def add_documentation(self, doc_path: Path, tool_name: str, category: str):
        """Add new documentation to the retriever"""
        with open(doc_path, 'r') as f:
            content = f.read()
        self.retriever.add_documentation(
            content=content,
            tool_name=tool_name,
            category=category,
            source=str(doc_path)
        )
        
    def save_docs_index(self, path: str):
        """Save the documentation index"""
        self.retriever.save_index(path)
        
    def load_docs_index(self, path: str):
        """Load a documentation index"""
        self.retriever.load_index(path)
