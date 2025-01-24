"""
Integration of RAG-enhanced LLM pipeline with existing code generation system.
"""
from pathlib import Path
from typing import Dict, Optional, List
import asyncio

from forge.rag_llm import RAGLLMPipeline
from forge.rag_retriever import RAGRetriever

class RAGCodeGenerator:
    """Code generator that uses RAG to generate code from documentation"""
    
    def __init__(self, pipeline: RAGLLMPipeline):
        """Initialize the code generator"""
        self.pipeline = pipeline
    
    async def generate_code(self, query: str, context: Optional[Dict] = None) -> str:
        """Generate code based on the query and documentation"""
        response = await self.pipeline.process_query(query)
        return response
    
    def add_documentation(self, doc_path: Path, tool_name: str, category: str):
        """Add new documentation to the retriever"""
        with open(doc_path, 'r') as f:
            content = f.read()
        self.pipeline.retriever.add_documentation(
            content=content,
            tool_name=tool_name,
            category=category,
            source=str(doc_path)
        )
        
    def save_docs_index(self, path: str):
        """Save the documentation index"""
        self.pipeline.retriever.save_index(path)
        
    def load_docs_index(self, path: str):
        """Load a documentation index"""
        self.pipeline.retriever.load_index(path)
